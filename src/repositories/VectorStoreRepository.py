import logging

import chromadb

logger = logging.getLogger(__name__)

# Stored in the collection metadata so we can detect when the configured embedder changed.
EMBEDDER_META_KEY = "embedder_id"


def _clear_chroma_system_cache() -> None:
    """Drop ChromaDB's per-process client cache so the next client reads fresh on-disk state."""
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


def build_summary_document(summary) -> tuple[str, dict]:
    """Build the embedded doc text + metadata for a summary (shared by bulk load and auto-embed)."""
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
    return doc_text, metadata


class VectorStoreRepository:
    """Wraps ChromaDB with a pluggable embedder (Gemini or local) for summary vector storage."""

    def __init__(self, persist_path: str, embedder):
        self._persist_path = persist_path
        self._embedder = embedder
        # Fresh read each request — avoids a stale cached client after another worker's reset
        # ("hnsw segment reader: Nothing found on disk").
        _clear_chroma_system_cache()
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._get_or_reset_collection()

    def _collection_metadata(self) -> dict:
        return {"hnsw:space": "cosine", EMBEDDER_META_KEY: self._embedder.id}

    def _get_or_reset_collection(self):
        """Get the collection, recreating it if the embedder changed (dims aren't interchangeable;
        safe — summaries live in SQLite and can be reloaded)."""
        collection = self._client.get_or_create_collection(
            name="summaries",
            metadata=self._collection_metadata(),
        )
        stored = (collection.metadata or {}).get(EMBEDDER_META_KEY)
        if stored == self._embedder.id:
            return collection

        if stored is not None:
            logger.warning(
                "Embedder changed (%s → %s); clearing vector store. Reload summaries to repopulate.",
                stored,
                self._embedder.id,
            )
        elif collection.count() > 0:
            logger.warning(
                "Vector store has no embedder stamp (legacy data); clearing to re-stamp with %s. "
                "Reload summaries to repopulate.",
                self._embedder.id,
            )

        # Tolerate a concurrent reset from another worker (collection may already be gone).
        try:
            self._client.delete_collection("summaries")
        except Exception:
            pass
        return self._client.get_or_create_collection(
            name="summaries",
            metadata=self._collection_metadata(),
        )

    def add_summary(self, summary_id: int, text: str, metadata: dict) -> None:
        doc_id = f"summary_{summary_id}"
        embeddings = self._embedder.embed([text])
        self._collection.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[text],
            metadatas=[metadata],
        )

    def search(self, query: str, top_k: int = 5, summary_ids: list[int] | None = None) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        query_embedding = self._embedder.embed([query])

        where_filter = None
        if summary_ids:
            where_filter = {"summary_id": {"$in": summary_ids}}

        try:
            results = self._collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, count),
                where=where_filter,
            )
        except Exception as e:
            # Treat a query failure (e.g. "hnsw segment reader: Nothing found on disk") as empty, not 500.
            logger.warning("Vector store query failed (treating as empty): %s", e)
            return []
        items = []
        for i in range(len(results["ids"][0])):
            items.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                }
            )
        return items

    def is_loaded(self, summary_id: int) -> bool:
        doc_id = f"summary_{summary_id}"
        try:
            result = self._collection.get(ids=[doc_id])
            return len(result["ids"]) > 0
        except Exception:
            return False

    def get_all(self):
        return self._collection.get(include=["documents", "metadatas", "embeddings"])

    def count(self) -> int:
        return self._collection.count()

    def delete_summary(self, summary_id: int) -> None:
        doc_id = f"summary_{summary_id}"
        try:
            self._collection.delete(ids=[doc_id])
        except Exception:
            pass

    def clear(self) -> None:
        self._client.delete_collection("summaries")
        self._collection = self._client.get_or_create_collection(
            name="summaries",
            metadata=self._collection_metadata(),
        )
