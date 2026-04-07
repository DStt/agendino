import logging

import chromadb
from google import genai

logger = logging.getLogger(__name__)


class VectorStoreRepository:
    """Wraps ChromaDB with Gemini embeddings for summary vector storage."""

    def __init__(self, persist_path: str, api_key: str, model: str):
        self._persist_path = persist_path
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name="summaries",
            metadata={"hnsw:space": "cosine"},
        )
        self._genai_client = genai.Client(api_key=api_key)
        self._model = model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        result = self._genai_client.models.embed_content(
            model=self._model,
            contents=texts,
        )
        embeddings = result.embeddings or []
        return [e.values for e in embeddings if e.values is not None]

    def add_summary(self, summary_id: int, text: str, metadata: dict) -> None:
        doc_id = f"summary_{summary_id}"
        embeddings = self._embed([text])
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
        query_embedding = self._embed([query])

        where_filter = None
        if summary_ids:
            where_filter = {"summary_id": {"$in": summary_ids}}

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, count),
            where=where_filter,
        )
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
            metadata={"hnsw:space": "cosine"},
        )
