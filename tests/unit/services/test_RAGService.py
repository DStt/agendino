import json

import pytest
from unittest.mock import MagicMock, patch

from services.RAGService import RAGService


def _context_docs():
    return [
        {
            "document": "doc body",
            "metadata": {"title": "Source title", "recording_name": "rec", "summary_id": 1},
            "distance": 0.1,
        }
    ]


class TestRAGParseMindMap:
    def test_valid_json(self):
        data = {"central_topic": "C", "branches": [], "connections": []}
        assert RAGService._parse_mind_map_json(json.dumps(data)) == data

    def test_repairs_malformed_json(self):
        result = RAGService._parse_mind_map_json('{"central_topic": "C", "branches": []')
        assert result["central_topic"] == "C"

    def test_garbage_returns_empty_structure(self):
        result = RAGService._parse_mind_map_json("not json")
        assert result["central_topic"] == "Knowledge Base"
        assert result["branches"] == []
        assert result["connections"] == []


class TestRAGProviderRouting:
    @staticmethod
    def _deepseek(text):
        ds = MagicMock()
        ds.is_configured = True
        ds.generate_chat.return_value = (text, False)
        return ds

    def test_ask_deepseek(self):
        ds = self._deepseek("answer text")
        service = RAGService(deepseek_service=ds, default_provider="deepseek")

        result = service.ask("question?", _context_docs())

        assert result["answer"] == "answer text"
        assert result["sources"][0]["title"] == "Source title"
        assert ds.generate_chat.call_args.kwargs["json_mode"] is False

    def test_ask_deepseek_not_configured_raises(self):
        service = RAGService(default_provider="deepseek")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.ask("q", _context_docs())

    def test_ask_gemini(self):
        with patch("services.RAGService.genai.Client") as client_cls:
            response = MagicMock()
            response.text = "gemini answer"
            client_cls.return_value.models.generate_content.return_value = response
            service = RAGService(api_key="fake", model="gemini-3.8-flash")

            result = service.ask("q", _context_docs(), provider="gemini")

        assert result["answer"] == "gemini answer"
        assert client_cls.return_value.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

    def test_ask_gemini_not_configured_raises(self):
        service = RAGService(api_key=None, default_provider="gemini")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.ask("q", _context_docs())

    def test_generate_mind_map_deepseek(self):
        raw = json.dumps({"central_topic": "C", "branches": [], "connections": []})
        ds = self._deepseek(raw)
        service = RAGService(deepseek_service=ds, default_provider="deepseek")

        result = service.generate_mind_map([{"id": 1, "title": "T", "tags": ["a"], "summary": "body"}])

        assert result["central_topic"] == "C"
        kwargs = ds.generate_chat.call_args.kwargs
        assert kwargs["json_mode"] is True
        assert "ID: 1" in kwargs["user_content"]

    def test_generate_mind_map_deepseek_not_configured_raises(self):
        service = RAGService(default_provider="deepseek")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.generate_mind_map([{"id": 1, "title": "T", "tags": [], "summary": "body"}])

    def test_generate_mind_map_gemini(self):
        with patch("services.RAGService.genai.Client") as client_cls:
            response = MagicMock()
            response.text = json.dumps({"central_topic": "Gem", "branches": [], "connections": []})
            client_cls.return_value.models.generate_content.return_value = response
            service = RAGService(api_key="fake")

            result = service.generate_mind_map(
                [{"id": 1, "title": "T", "tags": [], "summary": "body"}], provider="gemini"
            )

        assert result["central_topic"] == "Gem"
