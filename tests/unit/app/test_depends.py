from unittest.mock import MagicMock

import pytest

import app.depends as depends
from repositories.embedders import GeminiEmbedder, LocalEmbedder, OllamaEmbedder
from services.RAGService import OllamaRAGService, RAGService


@pytest.fixture
def configure(monkeypatch):
    """Set depends.config to a fixed dict and reset the embedder cache; stub genai.Client."""
    monkeypatch.setattr("google.genai.Client", lambda api_key=None: MagicMock())

    def _apply(**kw):
        monkeypatch.setattr(depends, "config", {"init": True, **kw})
        monkeypatch.setattr(depends, "_embedder", None)
    return _apply


class TestGetEmbedder:
    def test_ollama(self, configure):
        configure(EMBEDDING_PROVIDER="ollama", OLLAMA_BASE_URL="http://o:11434", OLLAMA_EMBEDDING_MODEL="bge-m3")
        assert isinstance(depends.get_embedder(), OllamaEmbedder)

    def test_local(self, configure):
        configure(EMBEDDING_PROVIDER="local", LOCAL_EMBEDDING_MODEL="BAAI/bge-m3")
        assert isinstance(depends.get_embedder(), LocalEmbedder)

    def test_gemini(self, configure):
        configure(EMBEDDING_PROVIDER="gemini", GEMINI_API_KEY="k", GEMINI_EMBEDDING_MODEL="m")
        assert isinstance(depends.get_embedder(), GeminiEmbedder)

    def test_cached_singleton(self, configure):
        configure(EMBEDDING_PROVIDER="ollama", OLLAMA_BASE_URL="http://o:11434", OLLAMA_EMBEDDING_MODEL="bge-m3")
        assert depends.get_embedder() is depends.get_embedder()


class TestGetRagService:
    def test_unset_follows_ollama_embeddings(self, configure):
        configure(EMBEDDING_PROVIDER="ollama", OLLAMA_BASE_URL="http://o:11434", OLLAMA_MODEL="m")
        assert isinstance(depends.get_rag_service(), OllamaRAGService)

    def test_local_is_synonym_for_ollama(self, configure):
        configure(EMBEDDING_PROVIDER="ollama", RAG_PROVIDER="local", OLLAMA_MODEL="m")
        assert isinstance(depends.get_rag_service(), OllamaRAGService)

    def test_explicit_gemini_overrides(self, configure):
        configure(EMBEDDING_PROVIDER="ollama", RAG_PROVIDER="gemini", GEMINI_API_KEY="k", GEMINI_MODEL="m")
        assert isinstance(depends.get_rag_service(), RAGService)

    def test_unset_gemini_when_embeddings_gemini(self, configure):
        configure(EMBEDDING_PROVIDER="gemini", GEMINI_API_KEY="k", GEMINI_MODEL="m")
        assert isinstance(depends.get_rag_service(), RAGService)
