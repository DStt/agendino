import json

import pytest
from unittest.mock import MagicMock, patch

from services.SummarizationService import SummarizationService


class TestSummarizationServiceParseResponse:
    """Unit tests for _parse_response (static method - no API key needed)."""

    def test_valid_json(self):
        raw = json.dumps(
            {
                "title": "Meeting Notes",
                "tags": ["meeting", "notes", "work"],
                "summary": "# Summary\nThis was a productive meeting.",
            }
        )
        result = SummarizationService._parse_response(raw)
        assert result["title"] == "Meeting Notes"
        assert result["tags"] == ["meeting", "notes", "work"]
        assert result["summary"] == "# Summary\nThis was a productive meeting."

    def test_valid_json_with_whitespace(self):
        raw = json.dumps(
            {
                "title": "  Padded Title  ",
                "tags": [" tag1 ", " tag2 "],
                "summary": "  Some summary  ",
            }
        )
        result = SummarizationService._parse_response(raw)
        assert result["title"] == "Padded Title"
        assert result["tags"] == ["tag1", "tag2"]
        assert result["summary"] == "Some summary"

    def test_tags_as_comma_string(self):
        raw = json.dumps(
            {
                "title": "Test",
                "tags": "tag1, tag2, tag3",
                "summary": "Summary text",
            }
        )
        result = SummarizationService._parse_response(raw)
        assert result["tags"] == ["tag1", "tag2", "tag3"]

    def test_empty_tags_filtered(self):
        raw = json.dumps(
            {
                "title": "Test",
                "tags": ["good", "", "  ", "also_good"],
                "summary": "Summary",
            }
        )
        result = SummarizationService._parse_response(raw)
        assert result["tags"] == ["good", "also_good"]

    def test_missing_fields_default(self):
        raw = json.dumps({})
        result = SummarizationService._parse_response(raw)
        assert result["title"] == ""
        assert result["tags"] == []
        assert result["summary"] == ""

    def test_truncated_appends_warning(self):
        raw = json.dumps(
            {
                "title": "Title",
                "tags": ["a"],
                "summary": "Some content",
            }
        )
        result = SummarizationService._parse_response(raw, truncated=True)
        assert "⚠️" in result["summary"]
        assert "truncated" in result["summary"]
        assert result["summary"].startswith("Some content")

    def test_truncated_empty_summary_no_warning(self):
        raw = json.dumps({"title": "Title", "tags": [], "summary": ""})
        result = SummarizationService._parse_response(raw, truncated=True)
        assert result["summary"] == ""

    def test_double_encoded_json_string(self):
        inner = json.dumps({"title": "Double", "tags": ["x"], "summary": "Body"})
        raw = json.dumps(inner)  # string of a JSON string
        result = SummarizationService._parse_response(raw)
        assert result["title"] == "Double"
        assert result["summary"] == "Body"

    def test_malformed_json_repaired(self):
        # Missing closing brace - json_repair should fix it
        raw = '{"title": "Broken", "tags": ["a"], "summary": "Text"'
        result = SummarizationService._parse_response(raw)
        assert result["title"] == "Broken"
        assert result["summary"] == "Text"

    def test_completely_invalid_falls_back_to_raw(self):
        raw = "This is not JSON at all, just plain text."
        result = SummarizationService._parse_response(raw)
        assert result["title"] == ""
        assert result["tags"] == []
        assert result["summary"] == raw.strip()

    def test_empty_string(self):
        result = SummarizationService._parse_response("")
        assert result["title"] == ""
        assert result["tags"] == []
        assert result["summary"] == ""


class TestSummarizationServiceProviderRouting:
    @staticmethod
    def _deepseek(raw, truncated=False):
        ds = MagicMock()
        ds.is_configured = True
        ds.generate_chat.return_value = (raw, truncated)
        return ds

    def test_deepseek_routing(self):
        raw = json.dumps({"title": "T", "tags": ["a"], "summary": "S"})
        ds = self._deepseek(raw)
        service = SummarizationService(deepseek_service=ds, default_provider="gemini")

        result = service.summarize("transcript", "prompt", provider="deepseek")

        assert result["title"] == "T"
        ds.generate_chat.assert_called_once()
        kwargs = ds.generate_chat.call_args.kwargs
        assert kwargs["json_mode"] is True
        assert kwargs["user_content"] == "transcript"

    def test_default_provider_deepseek(self):
        raw = json.dumps({"title": "D", "tags": [], "summary": "S"})
        ds = self._deepseek(raw)
        service = SummarizationService(deepseek_service=ds, default_provider="deepseek")

        assert service.summarize("t", "p")["title"] == "D"
        ds.generate_chat.assert_called_once()

    def test_deepseek_truncation_warning(self):
        raw = json.dumps({"title": "T", "tags": [], "summary": "S"})
        ds = self._deepseek(raw, truncated=True)
        service = SummarizationService(deepseek_service=ds)

        result = service.summarize("t", "p", provider="deepseek")
        assert "truncated" in result["summary"]

    def test_deepseek_not_configured_raises(self):
        service = SummarizationService(deepseek_service=None, default_provider="gemini")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.summarize("t", "p", provider="deepseek")

    def test_gemini_routing(self):
        with patch("services.SummarizationService.genai.Client") as client_cls:
            response = MagicMock()
            response.text = json.dumps({"title": "G", "tags": ["x"], "summary": "S"})
            response.candidates = []
            client_cls.return_value.models.generate_content.return_value = response

            service = SummarizationService(api_key="fake-key", model="gemini-3.8-flash")
            result = service.summarize("t", "p", provider="gemini")

        assert result["title"] == "G"
        assert client_cls.return_value.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

    def test_gemini_not_configured_raises(self):
        service = SummarizationService(api_key=None, default_provider="gemini")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.summarize("t", "p")
