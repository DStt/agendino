import json

import pytest

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
