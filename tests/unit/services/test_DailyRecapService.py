import json

import pytest
from unittest.mock import MagicMock, patch

from services.DailyRecapService import DailyRecapService


class TestDailyRecapParseResponse:
    def test_valid_json(self):
        raw = json.dumps(
            {
                "title": "Day",
                "highlights": ["h"],
                "recap": "r",
                "action_items": ["a"],
                "blockers": ["b"],
            }
        )
        result = DailyRecapService._parse_response(raw)
        assert result["title"] == "Day"
        assert result["highlights"] == ["h"]
        assert result["action_items"] == ["a"]
        assert result["blockers"] == ["b"]

    def test_missing_fields_defaulted(self):
        result = DailyRecapService._parse_response(json.dumps({"recap": "only"}))
        assert result["title"] == ""
        assert result["highlights"] == []
        assert result["action_items"] == []
        assert result["blockers"] == []
        assert result["recap"] == "only"

    def test_repairs_malformed_json(self):
        result = DailyRecapService._parse_response('{"title": "T", "recap": "R"')
        assert result["title"] == "T"
        assert result["recap"] == "R"

    def test_plain_text_fallback(self):
        result = DailyRecapService._parse_response("plain text recap")
        assert result["recap"] == "plain text recap"


class TestDailyRecapProviderRouting:
    @staticmethod
    def _deepseek(raw):
        ds = MagicMock()
        ds.is_configured = True
        ds.generate_chat.return_value = (raw, False)
        return ds

    def test_deepseek_routing(self):
        raw = json.dumps({"title": "Deep", "recap": "R"})
        ds = self._deepseek(raw)
        service = DailyRecapService(deepseek_service=ds, default_provider="deepseek")

        result = service.generate_recap(
            "2026-04-01",
            [{"title": "Event", "start_at": "09:00", "end_at": "10:00"}],
            [{"title": "Summary", "summary": "body", "tags": ["a"]}],
        )

        assert result["title"] == "Deep"
        kwargs = ds.generate_chat.call_args.kwargs
        assert kwargs["json_mode"] is True
        assert "Event" in kwargs["user_content"]
        assert "body" in kwargs["user_content"]

    def test_deepseek_not_configured_raises(self):
        service = DailyRecapService(default_provider="deepseek")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.generate_recap("2026-04-01", [], [])

    def test_gemini_routing(self):
        with patch("services.DailyRecapService.genai.Client") as client_cls:
            response = MagicMock()
            response.text = json.dumps({"title": "Gem", "recap": "R"})
            client_cls.return_value.models.generate_content.return_value = response
            service = DailyRecapService(api_key="fake", model="gemini-3.8-flash")

            result = service.generate_recap("2026-04-01", [], [], provider="gemini")

        assert result["title"] == "Gem"
        assert client_cls.return_value.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

    def test_gemini_not_configured_raises(self):
        service = DailyRecapService(api_key=None, default_provider="gemini")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.generate_recap("2026-04-01", [], [])
