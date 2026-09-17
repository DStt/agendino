from fastapi import APIRouter, Depends, Query

from app import depends
from controllers.CalendarController import CalendarController
from models.dto.CreateCalendarEventDTO import CreateCalendarEventDTO
from models.dto.LinkRecordingEventDTO import LinkRecordingEventDTO
from models.dto.UpdateCalendarEventDTO import UpdateCalendarEventDTO
from models.dto.SharedCalendarDTO import CreateSharedCalendarDTO, UpdateSharedCalendarDTO

router = APIRouter()


# ─── Calendar Events ─────────────────────────────────────────────


@router.get("/month/{year}/{month}")
def get_calendar_month(
    year: int,
    month: int,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.get_calendar_events_for_month(year, month)


@router.get("/day/{date_str}")
def get_calendar_day(
    date_str: str,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.get_calendar_events_for_day(date_str)


@router.get("/day-detail/{date_str}")
def get_day_detail(
    date_str: str,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.get_day_detail(date_str)


@router.post("/events")
def create_calendar_event(
    body: CreateCalendarEventDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.create_calendar_event(
        title=body.title,
        start_at=body.start_at,
        end_at=body.end_at,
        description=body.description,
        is_all_day=body.is_all_day,
        location=body.location,
        meeting_url=body.meeting_url,
    )


@router.patch("/events/{event_id}")
def update_calendar_event(
    event_id: int,
    body: UpdateCalendarEventDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    return calendar_controller.update_calendar_event(event_id, **kwargs)


@router.delete("/events/{event_id}")
def delete_calendar_event(
    event_id: int,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.delete_calendar_event(event_id)


@router.post("/link")
def link_recording_to_event(
    body: LinkRecordingEventDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.link_recording_to_event(body.recording_id, body.event_id)


@router.delete("/link")
def unlink_recording_from_event(
    body: LinkRecordingEventDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.unlink_recording_from_event(body.recording_id, body.event_id)


# ─── Daily Recap ─────────────────────────────────────────────────


@router.post("/recap/{date_str}")
def generate_daily_recap(
    date_str: str,
    provider: str | None = Query(None),
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.generate_daily_recap(date_str, provider=provider)


@router.get("/recap/{date_str}")
def get_daily_recap(
    date_str: str,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.get_daily_recap(date_str)


@router.delete("/recap/{date_str}")
def delete_daily_recap(
    date_str: str,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.delete_daily_recap(date_str)


# ─── Shared Calendars ────────────────────────────────────────────


@router.get("/shared")
def list_shared_calendars(
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.list_shared_calendars()


@router.post("/shared")
def create_shared_calendar(
    body: CreateSharedCalendarDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.create_shared_calendar(
        name=body.name,
        ical_url=body.ical_url,
        color=body.color,
        is_enabled=body.is_enabled,
        sync_interval_minutes=body.sync_interval_minutes,
    )


@router.post("/shared/sync-all")
def sync_all_shared_calendars(
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.sync_all_shared_calendars()


@router.post("/shared/validate")
def validate_ical_url(
    body: CreateSharedCalendarDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.validate_ical_url(body.ical_url)


@router.patch("/shared/{calendar_id}")
def update_shared_calendar(
    calendar_id: int,
    body: UpdateSharedCalendarDTO,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    return calendar_controller.update_shared_calendar(calendar_id, **kwargs)


@router.delete("/shared/{calendar_id}")
def delete_shared_calendar(
    calendar_id: int,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.delete_shared_calendar(calendar_id)


@router.post("/shared/{calendar_id}/sync")
def sync_shared_calendar(
    calendar_id: int,
    calendar_controller: CalendarController = Depends(depends.get_calendar_controller),
):
    return calendar_controller.sync_shared_calendar(calendar_id)
