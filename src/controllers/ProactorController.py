from __future__ import annotations

from datetime import datetime

from fastapi import Request
from fastapi.templating import Jinja2Templates

from repositories.SqliteDBRepository import SqliteDBRepository
from services.ProactorService import ProactorService


class ProactorController:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        template_path: str,
        proactor_service: ProactorService | None = None,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._templates = Jinja2Templates(directory=template_path)
        self._proactor_service = proactor_service or ProactorService()

    # ─── Web ──────────────────────────────────────────────────────

    def proactor_home(self, request: Request):
        return self._templates.TemplateResponse(
            request=request, name="dashboard/proactor.html", context={"active_page": "proactor"}
        )

    # ─── Analysis ─────────────────────────────────────────────────

    def analyze_date_range(self, start_date: str, end_date: str) -> dict:
        """Run proactive analysis on all calendar events in [start_date, end_date]."""
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return {"ok": False, "error": "Invalid date format — use YYYY-MM-DD"}

        if start_date > end_date:
            return {"ok": False, "error": "start_date must be before end_date"}

        events = self._sqlite_db_repository.get_calendar_events_for_range(start_date, end_date)
        event_dicts = [e.to_dict() for e in events]

        report = self._proactor_service.analyze_range(event_dicts)

        return {
            "ok": True,
            "start_date": start_date,
            "end_date": end_date,
            **report,
        }
