from __future__ import annotations

import logging
from datetime import datetime

from fastapi import Request
from fastapi.templating import Jinja2Templates

from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.VectorStoreRepository import VectorStoreRepository
from services.RAGService import RAGService

logger = logging.getLogger(__name__)


class RAGController:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        vector_store_repository: VectorStoreRepository,
        rag_service: RAGService,
        template_path: str,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._vector_store = vector_store_repository
        self._rag_service = rag_service
        self._templates = Jinja2Templates(directory=template_path)

    def home(self, request: Request):
        return self._templates.TemplateResponse(
            request=request, name="knowledge/home.html", context={"active_page": "knowledge"}
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
                # Build rich document text for better retrieval
                doc_text = ""
                if summary.title:
                    doc_text += f"Title: {summary.title}\n"
                if summary.tags:
                    doc_text += f"Tags: {summary.tags}\n"
                doc_text += f"\n{summary.summary}"

                metadata = {
                    "summary_id": summary.id,
                    "recording_name": summary.recording_name,
                    "title": summary.title or "",
                    "tags": summary.tags or "",
                    "version": summary.version,
                }

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

        results = self._vector_store.search(query, top_k, summary_ids=summary_ids)
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
        """Use Gemini to generate an AI-structured mind map from summaries."""
        summaries_map = self._sqlite_db_repository.get_latest_summaries_map()

        summaries_list = []
        for name, summary in summaries_map.items():
            if summary_ids and summary.id not in summary_ids:
                continue
            if not summary.summary or not summary.summary.strip():
                continue
            summaries_list.append(
                {
                    "id": summary.id,
                    "title": summary.title or name,
                    "tags": summary.tags.split(",") if summary.tags else [],
                    "summary": summary.summary,
                    "recording_name": summary.recording_name,
                }
            )

        if not summaries_list:
            return {"ok": False, "error": "No summaries to analyze"}

        try:
            result = self._rag_service.generate_mind_map(summaries_list)
        except Exception as e:
            return {"ok": False, "error": f"Mind map generation failed: {str(e)}"}

        return {"ok": True, "mind_map": result, "summary_count": len(summaries_list)}

    def clear_vector_store(self) -> dict:
        self._vector_store.clear()
        return {"ok": True, "message": "Vector store cleared"}
