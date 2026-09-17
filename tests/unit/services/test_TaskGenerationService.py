import json

import pytest
from unittest.mock import MagicMock, patch

from services.TaskGenerationService import TaskGenerationService


class TestTaskGenerationParseResponse:
    def test_parses_json_list(self):
        raw = json.dumps(
            [
                {
                    "title": "Task",
                    "description": "Desc",
                    "subtasks": [{"title": "Sub", "description": "Sub desc"}],
                }
            ]
        )
        tasks = TaskGenerationService._parse_response(raw)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Task"
        assert tasks[0]["subtasks"][0]["title"] == "Sub"

    def test_parses_tasks_object(self):
        raw = json.dumps({"tasks": [{"title": "T", "description": "D"}]})
        tasks = TaskGenerationService._parse_response(raw)
        assert tasks == [{"title": "T", "description": "D", "subtasks": []}]

    def test_skips_invalid_and_empty_titles(self):
        raw = json.dumps(["nope", {"title": "   "}, {"title": "valid"}])
        tasks = TaskGenerationService._parse_response(raw)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "valid"

    def test_double_encoded_json(self):
        inner = json.dumps([{"title": "Double", "description": "D"}])
        tasks = TaskGenerationService._parse_response(json.dumps(inner))
        assert tasks[0]["title"] == "Double"

    def test_repairs_malformed_json(self):
        raw = '{"tasks": [{"title": "Broken", "description": "D"}]'
        tasks = TaskGenerationService._parse_response(raw)
        assert tasks and tasks[0]["title"] == "Broken"

    def test_returns_empty_on_garbage(self):
        assert TaskGenerationService._parse_response("not json at all") == []


class TestTaskGenerationProviderRouting:
    @staticmethod
    def _deepseek(raw):
        ds = MagicMock()
        ds.is_configured = True
        ds.generate_chat.return_value = (raw, False)
        return ds

    def test_deepseek_routing(self):
        raw = json.dumps({"tasks": [{"title": "T", "description": "D"}]})
        ds = self._deepseek(raw)
        service = TaskGenerationService(deepseek_service=ds, default_provider="deepseek")

        tasks = service.generate_tasks("summary text", "summary title")

        assert tasks[0]["title"] == "T"
        kwargs = ds.generate_chat.call_args.kwargs
        assert kwargs["json_mode"] is True
        assert "summary title" in kwargs["user_content"]
        assert "summary text" in kwargs["user_content"]

    def test_deepseek_not_configured_raises(self):
        service = TaskGenerationService(default_provider="deepseek")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.generate_tasks("summary")

    def test_gemini_routing(self):
        with patch("services.TaskGenerationService.genai.Client") as client_cls:
            response = MagicMock()
            response.text = json.dumps([{"title": "G", "description": "D"}])
            client_cls.return_value.models.generate_content.return_value = response
            service = TaskGenerationService(api_key="fake", model="gemini-3.8-flash")

            tasks = service.generate_tasks("summary", provider="gemini")

        assert tasks[0]["title"] == "G"
        assert client_cls.return_value.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

    def test_gemini_not_configured_raises(self):
        service = TaskGenerationService(api_key=None, default_provider="gemini")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.generate_tasks("summary")
