from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime

import numpy as np
from fastapi import Request
from fastapi.templating import Jinja2Templates

from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.VectorStoreRepository import VectorStoreRepository, build_summary_document
from services.RAGService import RAGService

logger = logging.getLogger(__name__)

# Below this many summaries, skip clustering and use the single-shot mind map (fits the context fine).
MIN_CLUSTER_N = 12


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _kmeans(vectors: list[list[float]], k: int, seed: int = 0):
    """Cosine k-means via scikit-learn (L2-normalized → Euclidean ≈ cosine). Returns (labels, centroids)."""
    from sklearn.cluster import KMeans

    x = _normalize(np.asarray(vectors, dtype=float))
    k = max(1, min(k, len(x)))
    km = KMeans(n_clusters=k, random_state=seed, n_init=10)
    labels = km.fit_predict(x)
    return labels, km.cluster_centers_


def _central_topic(records: list[dict]) -> str:
    """Heuristic central topic: the most common tag across the included summaries (no extra LLM call)."""
    tags = Counter()
    for r in records:
        for tag in r.get("tags", []):
            tag = tag.strip()
            if tag:
                tags[tag] += 1
    return tags.most_common(1)[0][0] if tags else "Knowledge Base"


def _connections(centroids: list, branches: list[dict], top: int = 3, threshold: float = 0.5) -> list[dict]:
    """Top cross-branch links by centroid cosine similarity."""
    if len(branches) < 2:
        return []
    cn = _normalize(np.asarray(centroids, dtype=float))
    sims = cn @ cn.T
    pairs = sorted(
        ((sims[i][j], i, j) for i in range(len(branches)) for j in range(i + 1, len(branches))),
        reverse=True,
    )
    conns = []
    for sim, i, j in pairs[:top]:
        if sim < threshold:
            continue
        conns.append({"from": branches[i]["id"], "to": branches[j]["id"], "label": "related"})
    return conns


class RAGController:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        vector_store_repository: VectorStoreRepository,
        rag_service: RAGService,
        template_path: str,
        auth_enabled: bool = False,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._vector_store = vector_store_repository
        self._rag_service = rag_service
        self._templates = Jinja2Templates(directory=template_path)
        self._auth_enabled = auth_enabled

    def home(self, request: Request):
        return self._templates.TemplateResponse(
            request=request,
            name="knowledge/home.html",
            context={"active_page": "knowledge", "auth_enabled": self._auth_enabled},
        )

    @staticmethod
    def _parse_recording_datetime(bare_name: str) -> str | None:
        try:
            parts = bare_name.split("-")
            if len(parts) >= 2:
                dt_str = f"{parts[0]}-{parts[1]}"
                dt = datetime.strptime(dt_str, "%Y%b%d-%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            pass
        return None

    def get_stats(self) -> dict:
        total_summaries = len(self._sqlite_db_repository.get_latest_summaries_map())
        loaded_count = self._vector_store.count()
        return {
            "ok": True,
            "total_summaries": total_summaries,
            "loaded_count": loaded_count,
            # Hint the UI to (re)load: summaries exist but none are in the vector store — true for a
            # fresh store and after an embedder-change reset wipes it.
            "needs_reload": total_summaries > 0 and loaded_count == 0,
        }

    def list_summaries(self) -> dict:
        """Return a lightweight list of all available summaries (for the picker UI)."""
        summaries_map = self._sqlite_db_repository.get_latest_summaries_map()
        items = []
        for name, summary in summaries_map.items():
            if not summary.summary or not summary.summary.strip():
                continue
            items.append(
                {
                    "id": summary.id,
                    "title": summary.title or name,
                    "recording_name": summary.recording_name,
                    "tags": summary.tags.split(",") if summary.tags else [],
                }
            )
        # Sort chronologically descending (most recent first) by recording name
        items.sort(
            key=lambda s: self._parse_recording_datetime(s["recording_name"]) or "",
            reverse=True,
        )
        return {"ok": True, "summaries": items}

    def load_summaries(self) -> dict:
        """Load all latest summaries into the vector store."""
        summaries_map = self._sqlite_db_repository.get_latest_summaries_map()
        loaded = 0
        skipped = 0
        errors = []

        for name, summary in summaries_map.items():
            if not summary.summary or not summary.summary.strip():
                skipped += 1
                continue

            try:
                doc_text, metadata = build_summary_document(summary)
                self._vector_store.add_summary(summary.id, doc_text, metadata)
                loaded += 1
            except Exception as e:
                logger.warning("Failed to load summary %s: %s", name, e)
                errors.append(f"{name}: {str(e)}")

        return {
            "ok": True,
            "loaded": loaded,
            "skipped": skipped,
            "errors": errors,
            "total_in_store": self._vector_store.count(),
        }

    def search(self, query: str, top_k: int = 5, summary_ids: list[int] | None = None) -> dict:
        if self._vector_store.count() == 0:
            return {"ok": False, "error": "Vector store is empty. Load summaries first."}

        try:
            results = self._vector_store.search(query, top_k, summary_ids=summary_ids)
        except Exception as e:
            return {"ok": False, "error": f"Search failed: {str(e)}"}
        return {
            "ok": True,
            "results": results,
            "query": query,
        }

    def ask(self, question: str, top_k: int = 5, summary_ids: list[int] | None = None) -> dict:
        if self._vector_store.count() == 0:
            return {"ok": False, "error": "Vector store is empty. Load summaries first."}

        # Retrieve relevant docs
        context_docs = self._vector_store.search(question, top_k, summary_ids=summary_ids)

        # Generate answer using RAG
        try:
            result = self._rag_service.ask(question, context_docs)
        except Exception as e:
            return {"ok": False, "error": f"RAG query failed: {str(e)}"}

        return {
            "ok": True,
            "answer": result["answer"],
            "sources": result["sources"],
            "question": question,
        }

    def get_mind_map_data(self, summary_ids: list[int] | None = None) -> dict:
        """Build a tag-based mind map from summaries (fast, no AI call)."""
        summaries_map = self._sqlite_db_repository.get_latest_summaries_map()
        if not summaries_map:
            return {"ok": False, "error": "No summaries found"}

        nodes = []
        edges = []
        tag_nodes = {}

        for name, summary in summaries_map.items():
            if summary_ids and summary.id not in summary_ids:
                continue
            if not summary.summary or not summary.summary.strip():
                continue
            node, new_edges = self._build_summary_node(name, summary, tag_nodes)
            nodes.append(node)
            edges.extend(new_edges)

        nodes.extend(tag_nodes.values())

        return {
            "ok": True,
            "nodes": nodes,
            "edges": edges,
        }

    @staticmethod
    def _build_summary_node(name: str, summary, tag_nodes: dict) -> tuple[dict, list[dict]]:
        """Build a single summary node and its tag edges."""
        node_id = f"s_{summary.id}"
        node = {
            "id": node_id,
            "label": summary.title or name,
            "type": "summary",
            "summary_id": summary.id,
            "recording_name": summary.recording_name,
            "tags": summary.tags.split(",") if summary.tags else [],
            "title": f"<b>{summary.title or name}</b><br><small>{summary.recording_name}</small>",
        }

        edges = []
        if summary.tags:
            for tag in summary.tags.split(","):
                tag = tag.strip()
                if not tag:
                    continue
                tag_id = f"t_{tag}"
                if tag_id not in tag_nodes:
                    tag_nodes[tag_id] = {
                        "id": tag_id,
                        "label": tag,
                        "type": "tag",
                        "title": f"Tag: {tag}",
                    }
                edges.append({"from": node_id, "to": tag_id})

        return node, edges

    def generate_mind_map(self, summary_ids: list[int] | None = None) -> dict:
        """AI mind map: cluster vector-store embeddings, label one branch per cluster (scales past the
        context window). Needs summaries embedded (auto on summarize, or via "Load summaries")."""
        records = self._collect_records(summary_ids)
        if records is None:
            return {"ok": False, "error": "Vector store is empty. Load summaries first."}
        if not records:
            return {"ok": False, "error": "No summaries to analyze"}

        try:
            # Small corpus: the single-shot prompt fits fine — skip clustering.
            if len(records) < MIN_CLUSTER_N:
                result = self._rag_service.generate_mind_map(records)
                return {"ok": True, "mind_map": result, "summary_count": len(records)}
            mind_map = self._clustered_mind_map(records)
        except Exception as e:
            return {"ok": False, "error": f"Mind map generation failed: {str(e)}"}

        return {"ok": True, "mind_map": mind_map, "summary_count": len(records)}

    def _collect_records(self, summary_ids: list[int] | None) -> list[dict] | None:
        """Pull summaries (+ embeddings) from the vector store. None = empty store; [] = nothing matched."""
        data = self._vector_store.get_all()
        ids = data.get("ids") or []
        if not ids:
            return None
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        embeddings = data.get("embeddings")
        embeddings = embeddings if embeddings is not None else []

        records = []
        for i in range(len(ids)):
            meta = metadatas[i] or {}
            sid = meta.get("summary_id")
            if summary_ids and sid not in summary_ids:
                continue
            tags = meta.get("tags", "")
            records.append(
                {
                    "id": sid,
                    "title": meta.get("title", ""),
                    "tags": tags.split(",") if tags else [],
                    "summary": documents[i] if i < len(documents) else "",
                    "embedding": embeddings[i] if i < len(embeddings) else None,
                }
            )
        return records

    def _clustered_mind_map(self, records: list[dict]) -> dict:
        """Cluster embeddings → one labelled branch per cluster, with a heuristic topic + connections."""
        k = max(3, min(12, round(math.sqrt(len(records) / 2))))
        labels, centroids = _kmeans([r["embedding"] for r in records], k)

        branches = []
        branch_centroids = []
        for j in range(len(centroids)):
            members = [records[i] for i in range(len(records)) if labels[i] == j]
            if not members:
                continue
            branch = self._rag_service.label_cluster(members)
            bid = f"branch_{j + 1}"
            children = [
                {
                    "id": f"leaf_{j + 1}_{ci + 1}",
                    "label": child.get("label", ""),
                    "summary_ids": child.get("summary_ids", []),
                }
                for ci, child in enumerate(branch.get("children", []))
            ]
            branches.append({"id": bid, "label": branch.get("label") or f"Theme {j + 1}", "children": children})
            branch_centroids.append(centroids[j])

        return {
            "central_topic": _central_topic(records),
            "branches": branches,
            "connections": _connections(branch_centroids, branches),
        }

    def clear_vector_store(self) -> dict:
        self._vector_store.clear()
        return {"ok": True, "message": "Vector store cleared"}
