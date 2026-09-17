import os
from unittest.mock import MagicMock, patch

import pytest

from controllers.CalendarController import CalendarController
from controllers.DashboardController import DashboardController
from controllers.RAGController import RAGController


@pytest.fixture
def template_dir(tmp_path):
    d = tmp_path / "templates"
    d.mkdir()
    (d / "home.html").write_text("<html></html>")
    return str(d)


def _dashboard_controller(template_dir):
    sqlite_db = MagicMock()
    local_repo = MagicMock()
    system_prompts_repo = MagicMock()
    task_generation_service = MagicMock()
    summarization_service = MagicMock()
    deepseek_service = MagicMock()
    deepseek_service.is_configured = True
    deepseek_service.model = "deepseek-flash"

    controller = DashboardController(
        sqlite_db_repository=sqlite_db,
        local_recordings_repository=local_repo,
        transcription_service=MagicMock(),
        system_prompts_repository=system_prompts_repo,
        template_path=template_dir,
        publish_services={},
        task_generation_service=task_generation_service,
        summarization_service=summarization_service,
        deepseek_service=deepseek_service,
        default_ai_provider="deepseek",
    )
    return controller, {
        "sqlite_db": sqlite_db,
        "local_repo": local_repo,
        "system_prompts_repo": system_prompts_repo,
        "task_generation_service": task_generation_service,
        "summarization_service": summarization_service,
        "deepseek_service": deepseek_service,
    }


class TestDashboardControllerProviderPropagation:
    def test_summarize_passes_provider(self, template_dir):
        controller, mocks = _dashboard_controller(template_dir)
        mocks["sqlite_db"].get_transcript.return_value = "transcript"
        mocks["system_prompts_repo"].get_prompt_content.return_value = "prompt"
        mocks["summarization_service"].summarize.return_value = {
            "title": "T",
            "tags": [],
            "summary": "S",
        }

        controller.summarize_recording("test", "prompt_id", provider="deepseek")

        assert mocks["summarization_service"].summarize.call_args.kwargs["provider"] == "deepseek"

    def test_generate_tasks_passes_provider(self, template_dir):
        controller, mocks = _dashboard_controller(template_dir)
        summary = MagicMock()
        summary.id = 5
        summary.summary = "summary body"
        summary.title = "Summary title"
        mocks["sqlite_db"].get_summary_by_id.return_value = summary
        mocks["task_generation_service"].generate_tasks.return_value = [
            {"title": "Task", "description": "D", "subtasks": []}
        ]
        mocks["sqlite_db"].insert_tasks.side_effect = lambda tasks: tasks

        controller.generate_tasks(5, provider="deepseek")

        assert mocks["task_generation_service"].generate_tasks.call_args.kwargs["provider"] == "deepseek"

    def test_get_ai_providers_reports_models_and_default(self, template_dir):
        controller, mocks = _dashboard_controller(template_dir)
        mocks["summarization_service"]._client = object()
        mocks["summarization_service"]._model = "gemini-3.8-flash"

        config = controller.get_ai_providers()

        assert config["ok"] is True
        assert config["default_provider"] == "deepseek"
        by_id = {p["id"]: p for p in config["providers"]}
        assert by_id["gemini"]["configured"] is True
        assert by_id["gemini"]["model"] == "gemini-3.8-flash"
        assert by_id["deepseek"]["configured"] is True
        assert by_id["deepseek"]["model"] == "deepseek-flash"

    def test_get_ai_providers_unconfigured(self, template_dir):
        controller, mocks = _dashboard_controller(template_dir)
        mocks["summarization_service"]._client = None
        mocks["deepseek_service"].is_configured = False

        config = controller.get_ai_providers()

        by_id = {p["id"]: p for p in config["providers"]}
        assert by_id["gemini"]["configured"] is False
        assert by_id["deepseek"]["configured"] is False


class TestCalendarControllerProviderPropagation:
    def test_generate_daily_recap_passes_provider(self, template_dir):
        daily_recap_service = MagicMock()
        daily_recap_service.generate_recap.return_value = {"title": "Recap", "recap": "R"}
        sqlite_db = MagicMock()
        sqlite_db.save_daily_recap.side_effect = lambda recap: recap

        controller = CalendarController(
            sqlite_db_repository=sqlite_db,
            template_path=template_dir,
            daily_recap_service=daily_recap_service,
            ai_config={"providers": []},
        )

        with patch.object(
            controller,
            "get_day_detail",
            return_value={"events": [{"title": "E"}], "summaries": []},
        ):
            result = controller.generate_daily_recap("2026-04-01", provider="deepseek")

        assert result["ok"] is True
        assert daily_recap_service.generate_recap.call_args.kwargs["provider"] == "deepseek"

    def test_generate_daily_recap_without_service(self, template_dir):
        controller = CalendarController(
            sqlite_db_repository=MagicMock(),
            template_path=template_dir,
            daily_recap_service=None,
        )
        result = controller.generate_daily_recap("2026-04-01", provider="deepseek")
        assert result["ok"] is False
        assert "not configured" in result["error"]


class TestRAGControllerProviderPropagation:
    @staticmethod
    def _controller(template_dir):
        sqlite_db = MagicMock()
        vector_store = MagicMock()
        vector_store.count.return_value = 1
        vector_store.search.return_value = [
            {"document": "doc", "metadata": {"title": "T", "summary_id": 1}, "distance": 0.1}
        ]
        rag_service = MagicMock()
        rag_service.ask.return_value = {"answer": "A", "sources": []}
        rag_service.generate_mind_map.return_value = {"central_topic": "C", "branches": []}
        controller = RAGController(
            sqlite_db_repository=sqlite_db,
            vector_store_repository=vector_store,
            rag_service=rag_service,
            template_path=template_dir,
        )
        return controller, sqlite_db, vector_store, rag_service

    def test_ask_passes_provider(self, template_dir):
        controller, _, _, rag_service = self._controller(template_dir)

        result = controller.ask("question?", provider="deepseek")

        assert result["ok"] is True
        assert rag_service.ask.call_args.kwargs["provider"] == "deepseek"

    def test_generate_mind_map_passes_provider(self, template_dir):
        controller, sqlite_db, _, rag_service = self._controller(template_dir)
        summary = MagicMock()
        summary.id = 1
        summary.title = "Title"
        summary.tags = "a,b"
        summary.summary = "body"
        summary.recording_name = "rec"
        sqlite_db.get_latest_summaries_map.return_value = {"rec": summary}

        result = controller.generate_mind_map(provider="deepseek")

        assert result["ok"] is True
        assert rag_service.generate_mind_map.call_args.kwargs["provider"] == "deepseek"
