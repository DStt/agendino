"""Proactive calendar analysis service.

Detects scheduling issues like overlapping events, back-to-back meetings,
gaps, and overloaded days — all pure logic, no AI required.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Thresholds (configurable later)
BACK_TO_BACK_THRESHOLD_MIN = 5  # Events with < 5 min gap
SHORT_GAP_THRESHOLD_MIN = 15  # Gaps shorter than 15 min flagged as "tight"
LONG_GAP_THRESHOLD_MIN = 120  # Gaps longer than 2 h flagged as "idle window"
BUSY_DAY_HOURS = 6  # More than 6 h of meetings → overloaded


def _parse_dt(dt_str: str) -> datetime | None:
    """Best-effort parse of datetime strings stored in the DB."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _day_boundary(base: datetime, hour: int) -> datetime:
    """Return *base* date at *hour*:00.  Handles hour=24 as next-day 00:00."""
    if hour >= 24:
        return base.replace(hour=0, minute=0, second=0) + timedelta(days=1)
    return base.replace(hour=hour, minute=0, second=0)


def _fmt_hour(hour: int) -> str:
    """Format an hour value as HH:00, handling 24 → '24:00'."""
    return f"{hour:02d}:00"


def _fmt_time(dt: datetime, day_base: datetime) -> str:
    """Format *dt* as HH:MM relative to *day_base*.  Shows '24:00' for next-day midnight."""
    if dt.date() > day_base.date() and dt.hour == 0 and dt.minute == 0:
        return "24:00"
    return dt.strftime("%H:%M")


def _timed_events(events: list[dict]) -> list[dict]:
    """Filter and parse events that have valid start/end times (skip all-day)."""
    result = []
    for ev in events:
        if ev.get("is_all_day"):
            continue
        start = _parse_dt(ev.get("start_at", ""))
        end = _parse_dt(ev.get("end_at", ""))
        if start and end:
            result.append({**ev, "_start": start, "_end": end})
    result.sort(key=lambda e: e["_start"])
    return result


def _event_ref(ev: dict) -> dict:
    """Extract a lightweight reference dict from a timed event."""
    return {
        "id": ev.get("id"),
        "title": ev.get("title"),
        "start_at": ev.get("start_at"),
        "end_at": ev.get("end_at"),
        "calendar_name": ev.get("calendar_name"),
        "calendar_color": ev.get("calendar_color"),
    }


def _classify_gap(gap_min: float) -> str:
    """Classify a gap by duration."""
    if gap_min < SHORT_GAP_THRESHOLD_MIN:
        return "short"
    if gap_min >= LONG_GAP_THRESHOLD_MIN:
        return "idle_window"
    return "available"


def _overlap_severity(minutes: float) -> str:
    """Classify overlap severity by duration."""
    if minutes >= 30:
        return "high"
    if minutes >= 10:
        return "medium"
    return "low"


class ProactorService:
    """Stateless service — all methods accept pre-fetched event dicts."""

    # ── Overlaps ─────────────────────────────────────────────────
    @staticmethod
    def detect_overlaps(events: list[dict]) -> list[dict]:
        """Return pairs of events whose time ranges overlap."""
        timed = _timed_events(events)
        overlaps: list[dict] = []
        for i in range(len(timed)):
            for j in range(i + 1, len(timed)):
                a, b = timed[i], timed[j]
                if b["_start"] >= a["_end"]:
                    break
                overlap_minutes = (min(a["_end"], b["_end"]) - b["_start"]).total_seconds() / 60
                overlaps.append(
                    {
                        "event_a": _event_ref(a),
                        "event_b": _event_ref(b),
                        "overlap_minutes": round(overlap_minutes, 1),
                        "severity": _overlap_severity(overlap_minutes),
                    }
                )
        return overlaps

    # ── Back-to-back meetings ────────────────────────────────────
    @staticmethod
    def detect_back_to_back(events: list[dict], threshold_min: int = BACK_TO_BACK_THRESHOLD_MIN) -> list[dict]:
        """Consecutive events with less than *threshold_min* gap between them."""
        timed = _timed_events(events)
        pairs: list[dict] = []
        for i in range(len(timed) - 1):
            a, b = timed[i], timed[i + 1]
            gap = (b["_start"] - a["_end"]).total_seconds() / 60
            if 0 <= gap < threshold_min:
                pairs.append(
                    {
                        "event_a": _event_ref(a),
                        "event_b": _event_ref(b),
                        "gap_minutes": round(gap, 1),
                    }
                )
        return pairs

    # ── Gap analysis ─────────────────────────────────────────────
    @staticmethod
    def _build_gap(date_key: str, start_time: datetime, end_time: datetime) -> dict | None:
        """Build a single gap dict if the duration is >= 1 minute."""
        gap_min = (end_time - start_time).total_seconds() / 60
        if gap_min < 1:
            return None
        return {
            "date": date_key,
            "start": start_time.strftime("%H:%M"),
            "end": end_time.strftime("%H:%M"),
            "minutes": round(gap_min, 1),
            "kind": _classify_gap(gap_min),
        }

    @staticmethod
    def detect_gaps(events: list[dict], work_start_hour: int = 0, work_end_hour: int = 24) -> list[dict]:
        """Find free slots between events within the given hour window."""
        # Group events by date
        date_events: dict[str, list] = {}
        for ev in _timed_events(events):
            date_key = ev["_start"].strftime("%Y-%m-%d")
            date_events.setdefault(date_key, []).append(ev)

        gaps: list[dict] = []
        for date_key, evs in sorted(date_events.items()):
            base = datetime.strptime(date_key, "%Y-%m-%d")
            ws = _day_boundary(base, work_start_hour)
            we = _day_boundary(base, work_end_hour)
            cursor = ws

            for ev in evs:
                if cursor < ev["_start"] <= we:
                    gap = ProactorService._build_gap(date_key, cursor, ev["_start"])
                    if gap:
                        gaps.append(gap)
                cursor = max(cursor, ev["_end"])

            # Trailing gap until end of workday
            if cursor < we:
                gap = ProactorService._build_gap(date_key, cursor, we)
                if gap:
                    gaps.append(gap)

        return gaps

    # ── Busy-day detection ───────────────────────────────────────
    @staticmethod
    def assess_day_load(events: list[dict], threshold_hours: float = BUSY_DAY_HOURS) -> list[dict]:
        """Per-day meeting load.  Flags days exceeding *threshold_hours*."""
        date_totals: dict[str, float] = {}
        date_counts: dict[str, int] = {}

        for ev in _timed_events(events):
            date_key = ev["_start"].strftime("%Y-%m-%d")
            duration_h = (ev["_end"] - ev["_start"]).total_seconds() / 3600
            date_totals[date_key] = date_totals.get(date_key, 0) + duration_h
            date_counts[date_key] = date_counts.get(date_key, 0) + 1

        return [
            {
                "date": dk,
                "total_hours": round(date_totals[dk], 2),
                "event_count": date_counts[dk],
                "overloaded": date_totals[dk] >= threshold_hours,
            }
            for dk in sorted(date_totals)
        ]

    # ── Day timeline (visual) ───────────────────────────────────
    @staticmethod
    def build_day_timelines(events: list[dict], work_start_hour: int = 0, work_end_hour: int = 24) -> list[dict]:
        """Build per-day timelines with meeting blocks and free slots for visualisation.

        Each day contains a list of segments (type=meeting or type=free) that tile
        the day window from *work_start_hour* to *work_end_hour*.
        """
        work_span_min = (work_end_hour - work_start_hour) * 60

        date_events: dict[str, list] = {}
        for ev in _timed_events(events):
            date_key = ev["_start"].strftime("%Y-%m-%d")
            date_events.setdefault(date_key, []).append(ev)

        timelines: list[dict] = []
        for date_key, evs in sorted(date_events.items()):
            base = datetime.strptime(date_key, "%Y-%m-%d")
            ws = _day_boundary(base, work_start_hour)
            we = _day_boundary(base, work_end_hour)
            cursor = ws
            segments: list[dict] = []

            for ev in evs:
                ev_start = max(ev["_start"], ws)
                ev_end = min(ev["_end"], we)
                if ev_start >= we or ev_end <= ws:
                    continue  # entirely outside day window

                # Free gap before this event
                if cursor < ev_start:
                    gap_min = (ev_start - cursor).total_seconds() / 60
                    segments.append(
                        {
                            "type": "free",
                            "start": _fmt_time(cursor, base),
                            "end": _fmt_time(ev_start, base),
                            "minutes": round(gap_min, 1),
                            "pct": round(gap_min / work_span_min * 100, 2),
                            "kind": _classify_gap(gap_min),
                        }
                    )

                # Meeting block
                mtg_min = (ev_end - ev_start).total_seconds() / 60
                if mtg_min > 0:
                    segments.append(
                        {
                            "type": "meeting",
                            "start": _fmt_time(ev_start, base),
                            "end": _fmt_time(ev_end, base),
                            "minutes": round(mtg_min, 1),
                            "pct": round(mtg_min / work_span_min * 100, 2),
                            "title": ev.get("title", ""),
                            "calendar_name": ev.get("calendar_name"),
                            "calendar_color": ev.get("calendar_color"),
                        }
                    )

                cursor = max(cursor, ev_end)

            # Trailing free slot
            if cursor < we:
                gap_min = (we - cursor).total_seconds() / 60
                segments.append(
                    {
                        "type": "free",
                        "start": _fmt_time(cursor, base),
                        "end": _fmt_time(we, base),
                        "minutes": round(gap_min, 1),
                        "pct": round(gap_min / work_span_min * 100, 2),
                        "kind": _classify_gap(gap_min),
                    }
                )

            total_free = sum(s["minutes"] for s in segments if s["type"] == "free")
            total_busy = sum(s["minutes"] for s in segments if s["type"] == "meeting")

            timelines.append(
                {
                    "date": date_key,
                    "segments": segments,
                    "total_free_min": round(total_free, 1),
                    "total_busy_min": round(total_busy, 1),
                    "work_start": _fmt_hour(work_start_hour),
                    "work_end": _fmt_hour(work_end_hour),
                }
            )

        return timelines

    # ── Aggregate analysis ───────────────────────────────────────
    def analyze_range(self, events: list[dict]) -> dict:
        """Run all checks on the event list and return a unified report."""
        overlaps = self.detect_overlaps(events)
        back_to_back = self.detect_back_to_back(events)
        gaps = self.detect_gaps(events)
        day_load = self.assess_day_load(events)
        day_timelines = self.build_day_timelines(events)

        overloaded_days = [d for d in day_load if d["overloaded"]]

        issue_count = len(overlaps) + len(back_to_back) + len(overloaded_days)
        if issue_count == 0:
            health = "good"
        elif issue_count <= 3:
            health = "fair"
        else:
            health = "poor"

        return {
            "overlaps": overlaps,
            "back_to_back": back_to_back,
            "gaps": gaps,
            "day_load": day_load,
            "day_timelines": day_timelines,
            "summary": {
                "total_events": len(events),
                "overlap_count": len(overlaps),
                "back_to_back_count": len(back_to_back),
                "overloaded_days": len(overloaded_days),
                "free_slots": len([g for g in gaps if g["kind"] == "available"]),
                "health": health,
            },
        }
