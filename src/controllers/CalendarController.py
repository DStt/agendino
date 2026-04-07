from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import Request
from fastapi.templating import Jinja2Templates

from models.DBCalendarEvent import DBCalendarEvent
from models.DBDailyRecap import DBDailyRecap
from models.DBSharedCalendar import DBSharedCalendar
from repositories.SqliteDBRepository import SqliteDBRepository
from services.DailyRecapService import DailyRecapService
from services.ICalSyncService import ICalSyncService

logger = logging.getLogger(__name__)


class CalendarController:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        template_path: str,
        daily_recap_service: DailyRecapService | None = None,
        ical_sync_service: ICalSyncService | None = None,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._templates = Jinja2Templates(directory=template_path)
        self._daily_recap_service = daily_recap_service
        self._ical_sync_service = ical_sync_service or ICalSyncService()

    # ─── Web ──────────────────────────────────────────────────────

    def calendar_home(self, request: Request):
        self._auto_sync_calendars()
        return self._templates.TemplateResponse(request=request, name="calendar.html")

    def _auto_sync_calendars(self):
        try:
            calendars = self._sqlite_db_repository.get_shared_calendars()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for cal in calendars:
                if not cal.is_enabled:
                    continue
                should_sync = False
                if not cal.last_synced_at:
                    should_sync = True
                else:
                    try:
                        last_synced = datetime.fromisoformat(cal.last_synced_at.replace(" ", "T"))
                        minutes_since = (now - last_synced).total_seconds() / 60.0
                        if minutes_since >= cal.sync_interval_minutes:
                            should_sync = True
                    except Exception as e:
                        logger.warning("Failed to parse last_synced_at for calendar %s: %s", cal.id, e)
                        should_sync = True

                if should_sync:
                    logger.info("Auto-syncing calendar: %s (ID: %s)", cal.name, cal.id)
                    try:
                        self._do_sync_calendar(cal)
                    except Exception as e:
                        logger.error("Failed to sync calendar %s: %s", cal.id, e)
        except Exception as e:
            logger.error("Error in auto sync process: %s", e)

    # ─── Calendar Events ──────────────────────────────────────────

    def get_calendar_events_for_month(self, year: int, month: int) -> dict:
        events = self._sqlite_db_repository.get_calendar_events_for_month(year, month)
        recap_dates = self._sqlite_db_repository.get_daily_recaps_for_month(year, month)
        shared_calendars = self._sqlite_db_repository.get_shared_calendars()
        return {
            "ok": True,
            "year": year,
            "month": month,
            "events": [e.to_dict() for e in events],
            "recap_dates": recap_dates,
            "shared_calendars": [c.to_dict() for c in shared_calendars],
        }

    def get_calendar_events_for_day(self, date_str: str) -> dict:
        events = self._sqlite_db_repository.get_calendar_events_for_day(date_str)
        return {
            "ok": True,
            "date": date_str,
            "events": [e.to_dict() for e in events],
        }

    def get_day_detail(self, date_str: str) -> dict:
        """Full day detail: events, recordings, summaries, and stored recap for a day."""
        events = self._sqlite_db_repository.get_calendar_events_for_day(date_str)
        recordings = self._sqlite_db_repository.get_recordings_for_day(date_str)

        # Collect summaries for all recordings on this day
        summaries = []
        for rec in recordings:
            rec_summaries = self._sqlite_db_repository.get_summaries(rec["name"])
            if rec_summaries:
                latest = rec_summaries[0]
                summaries.append(
                    {
                        "summary_id": latest.id,
                        "recording_id": rec["recording_id"],
                        "recording_name": latest.recording_name,
                        "title": latest.title or "",
                        "tags": latest.tags.split(",") if latest.tags else [],
                        "summary": latest.summary,
                        "created_at": latest.created_at.isoformat() if latest.created_at else None,
                    }
                )

        # Include stored daily recap if it exists
        stored_recap = self._sqlite_db_repository.get_daily_recap(date_str)

        return {
            "ok": True,
            "date": date_str,
            "events": [e.to_dict() for e in events],
            "recordings": recordings,
            "summaries": summaries,
            "recap": stored_recap.to_dict() if stored_recap else None,
        }

    def create_calendar_event(
        self,
        title: str,
        start_at: str,
        end_at: str,
        description: str | None = None,
        is_all_day: bool = False,
        location: str | None = None,
        meeting_url: str | None = None,
    ) -> dict:
        event = DBCalendarEvent(
            id=None,
            title=title,
            description=description,
            start_at=start_at,
            end_at=end_at,
            is_all_day=is_all_day,
            location=location,
            meeting_url=meeting_url,
        )
        saved = self._sqlite_db_repository.insert_calendar_event(event)
        return {"ok": True, "event": saved.to_dict()}

    def update_calendar_event(self, event_id: int, **kwargs) -> dict:
        updated = self._sqlite_db_repository.update_calendar_event(event_id, **kwargs)
        if not updated:
            return {"ok": False, "error": f"Event '{event_id}' not found"}
        return {"ok": True, "event": updated.to_dict()}

    def delete_calendar_event(self, event_id: int) -> dict:
        deleted = self._sqlite_db_repository.delete_calendar_event(event_id)
        if not deleted:
            return {"ok": False, "error": f"Event '{event_id}' not found"}
        return {"ok": True, "deleted": event_id}

    def link_recording_to_event(self, recording_id: int, event_id: int) -> dict:
        self._sqlite_db_repository.link_recording_to_event(recording_id, event_id)
        event = self._sqlite_db_repository.get_calendar_event_by_id(event_id)
        return {"ok": True, "event": event.to_dict() if event else None}

    def unlink_recording_from_event(self, recording_id: int, event_id: int) -> dict:
        self._sqlite_db_repository.unlink_recording_from_event(recording_id, event_id)
        event = self._sqlite_db_repository.get_calendar_event_by_id(event_id)
        return {"ok": True, "event": event.to_dict() if event else None}

    # ─── Shared Calendars ─────────────────────────────────────────

    def list_shared_calendars(self) -> dict:
        calendars = self._sqlite_db_repository.get_shared_calendars()
        return {"ok": True, "calendars": [c.to_dict() for c in calendars]}

    def create_shared_calendar(
        self,
        name: str,
        ical_url: str,
        color: str = "#0d6efd",
        is_enabled: bool = True,
        sync_interval_minutes: int = 30,
    ) -> dict:
        # Validate the URL first
        validation = self._ical_sync_service.validate_url(ical_url)
        if not validation.get("ok"):
            return {"ok": False, "error": f"Invalid iCal URL: {validation.get('error', 'Unknown error')}"}

        cal = DBSharedCalendar(
            id=None,
            name=name or validation.get("calendar_name") or "Shared Calendar",
            ical_url=ical_url,
            color=color,
            is_enabled=is_enabled,
            sync_interval_minutes=sync_interval_minutes,
        )
        saved = self._sqlite_db_repository.insert_shared_calendar(cal)

        # Auto-sync on creation
        if is_enabled:
            try:
                self._do_sync_calendar(saved)
            except Exception:
                pass  # Don't fail creation if initial sync fails

        return {"ok": True, "calendar": saved.to_dict()}

    def update_shared_calendar(self, calendar_id: int, **kwargs) -> dict:
        updated = self._sqlite_db_repository.update_shared_calendar(calendar_id, **kwargs)
        if not updated:
            return {"ok": False, "error": f"Calendar '{calendar_id}' not found"}
        return {"ok": True, "calendar": updated.to_dict()}

    def delete_shared_calendar(self, calendar_id: int) -> dict:
        deleted = self._sqlite_db_repository.delete_shared_calendar(calendar_id)
        if not deleted:
            return {"ok": False, "error": f"Calendar '{calendar_id}' not found"}
        return {"ok": True, "deleted": calendar_id}

    def sync_shared_calendar(self, calendar_id: int) -> dict:
        cal = self._sqlite_db_repository.get_shared_calendar_by_id(calendar_id)
        if not cal:
            return {"ok": False, "error": f"Calendar '{calendar_id}' not found"}
        return self._do_sync_calendar(cal)

    def sync_all_shared_calendars(self) -> dict:
        calendars = self._sqlite_db_repository.get_shared_calendars()
        results = []
        for cal in calendars:
            if not cal.is_enabled:
                results.append({"id": cal.id, "name": cal.name, "skipped": True})
                continue
            result = self._do_sync_calendar(cal)
            results.append({"id": cal.id, "name": cal.name, **result})
        return {"ok": True, "results": results}

    def _do_sync_calendar(self, cal: DBSharedCalendar) -> dict:
        provider_name = f"ical:{cal.id}"
        try:
            events = self._ical_sync_service.fetch_and_parse(
                ical_url=cal.ical_url,
                provider_name=provider_name,
            )
            stats = self._sqlite_db_repository.sync_shared_calendar_events(
                calendar_id=cal.id,
                provider_name=provider_name,
                events=events,
            )
            return {
                "ok": True,
                "calendar_id": cal.id,
                "name": cal.name,
                **stats,
            }
        except Exception as e:
            error_msg = str(e)
            self._sqlite_db_repository.set_shared_calendar_error(cal.id, error_msg)
            return {"ok": False, "error": f"Sync failed: {error_msg}"}

    def validate_ical_url(self, ical_url: str) -> dict:
        return self._ical_sync_service.validate_url(ical_url)

    # ─── Daily Recap ──────────────────────────────────────────────

    def generate_daily_recap(self, date_str: str) -> dict:
        if not self._daily_recap_service:
            return {"ok": False, "error": "Daily recap service not configured (set GEMINI_API_KEY)"}

        day_detail = self.get_day_detail(date_str)
        events = day_detail.get("events", [])
        summaries = day_detail.get("summaries", [])

        if not events and not summaries:
            return {"ok": False, "error": "No events or summaries found for this day"}

        try:
            recap_data = self._daily_recap_service.generate_recap(date_str, events, summaries)
        except Exception as e:
            return {"ok": False, "error": f"Recap generation failed: {str(e)}"}

        # Persist the recap
        db_recap = DBDailyRecap.from_recap_dict(date_str, recap_data)
        saved = self._sqlite_db_repository.save_daily_recap(db_recap)

        return {"ok": True, "date": date_str, "recap": saved.to_dict()}

    def get_daily_recap(self, date_str: str) -> dict:
        stored = self._sqlite_db_repository.get_daily_recap(date_str)
        if not stored:
            return {"ok": False, "error": "No recap found for this date"}
        return {"ok": True, "date": date_str, "recap": stored.to_dict()}

    def delete_daily_recap(self, date_str: str) -> dict:
        deleted = self._sqlite_db_repository.delete_daily_recap(date_str)
        if not deleted:
            return {"ok": False, "error": "No recap found for this date"}
        return {"ok": True, "deleted": date_str}
