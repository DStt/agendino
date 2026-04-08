import json
import os
import sqlite3

from models.DBCalendarEvent import DBCalendarEvent
from models.DBDailyRecap import DBDailyRecap
from models.DBRecording import DBRecording
from models.DBSummary import DBSummary
from models.DBTask import DBTask
from models.DBSharedCalendar import DBSharedCalendar


class SqliteDBRepository:
    def __init__(self, db_name: str, db_path: str, init_sql_script: str):
        self._db_path = os.path.join(db_path, db_name)
        if not os.path.exists(self._db_path):
            self._initialize_db(init_sql_script)
        self._ensure_recording_columns()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize_db(self, init_sql_script: str) -> None:
        with open(init_sql_script, "r") as f:
            sql = f.read()
        conn = self._connect()
        conn.executescript(sql)
        conn.commit()
        conn.close()

    def _ensure_recording_columns(self) -> None:
        """Migration: add file_extension, recorded_at, and folder columns if missing on existing DB."""
        conn = self._connect()
        try:
            try:
                conn.execute("SELECT file_extension FROM recording LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE recording ADD COLUMN file_extension TEXT NOT NULL DEFAULT 'hda'")
                conn.commit()
            try:
                conn.execute("SELECT recorded_at FROM recording LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE recording ADD COLUMN recorded_at TEXT DEFAULT NULL")
                conn.commit()
            try:
                conn.execute("SELECT folder FROM recording LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE recording ADD COLUMN folder TEXT NOT NULL DEFAULT '/'")
                conn.commit()
        finally:
            conn.close()

    def get_recordings(self) -> list[DBRecording]:
        conn = self._connect()
        try:
            result = conn.execute(
                "SELECT id, name, label, duration, file_extension, recorded_at, created_at, transcript, folder "
                "FROM recording"
            )
            db_files = result.fetchall()
            recordings = [DBRecording.from_dict(row) for row in db_files]
            for rec in recordings:
                self._hydrate_latest_summary_fields(conn, rec)
            return recordings
        finally:
            conn.close()

    def get_recording_by_name(self, name: str) -> DBRecording | None:
        conn = self._connect()
        try:
            result = conn.execute(
                "SELECT id, name, label, duration, file_extension, recorded_at, created_at, transcript, folder "
                "FROM recording WHERE name = ?",
                (name,),
            )
            row = result.fetchone()
            if row:
                rec = DBRecording.from_dict(row)
                self._hydrate_latest_summary_fields(conn, rec)
                return rec
            return None
        finally:
            conn.close()

    @staticmethod
    def _hydrate_latest_summary_fields(conn: sqlite3.Connection, rec: DBRecording) -> None:
        latest = conn.execute(
            """
            SELECT summary, title, tags, notion_url
            FROM summary
            WHERE recording_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (rec.id,),
        ).fetchone()
        if latest:
            rec.summary = latest["summary"]
            rec.title = latest["title"]
            rec.tags = latest["tags"]
            rec.notion_url = latest["notion_url"]

    def insert_recording(self, db_recording: DBRecording) -> int:
        conn = self._connect()
        try:
            result = conn.execute(
                "INSERT INTO recording (id, name, label, duration, file_extension, created_at, transcript, folder) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    db_recording.id,
                    db_recording.name,
                    db_recording.label,
                    db_recording.duration,
                    db_recording.file_extension,
                    db_recording.created_at,
                    db_recording.transcript,
                    db_recording.folder,
                ),
            )
            conn.commit()
            return result.lastrowid
        finally:
            conn.close()

    def save_transcript(self, name: str, transcript: str) -> None:
        conn = self._connect()
        try:
            conn.execute("UPDATE recording SET transcript = ? WHERE name = ?", (transcript, name))
            conn.commit()
        finally:
            conn.close()

    def update_recording(self, name: str, recorded_at: str | None = None, duration: int | None = None) -> bool:
        """Update recording fields (recorded_at, duration)."""
        conn = self._connect()
        try:
            existing = conn.execute("SELECT id FROM recording WHERE name = ?", (name,)).fetchone()
            if not existing:
                return False
            updates = []
            params = []
            if recorded_at is not None:
                updates.append("recorded_at = ?")
                params.append(recorded_at)
            if duration is not None:
                updates.append("duration = ?")
                params.append(duration)
            if not updates:
                return False
            params.append(name)
            conn.execute(f"UPDATE recording SET {', '.join(updates)} WHERE name = ?", params)
            conn.commit()
            return True
        finally:
            conn.close()

    def update_transcript(self, name: str, transcript: str) -> bool:
        conn = self._connect()
        try:
            result = conn.execute("UPDATE recording SET transcript = ? WHERE name = ?", (transcript, name))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def get_transcript(self, name: str) -> str | None:
        conn = self._connect()
        try:
            result = conn.execute("SELECT transcript FROM recording WHERE name = ?", (name,))
            row = result.fetchone()
            if row:
                return row["transcript"]
            return None
        finally:
            conn.close()

    @staticmethod
    def _next_summary_version(conn: sqlite3.Connection, recording_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_version FROM summary WHERE recording_id = ?", (recording_id,)
        ).fetchone()
        return int(row["max_version"]) + 1

    def save_summarization_result(
        self, name: str, summary: str, title: str, tags: str, prompt_id: str | None = None
    ) -> DBSummary:
        conn = self._connect()
        try:
            recording_row = conn.execute("SELECT id FROM recording WHERE name = ?", (name,)).fetchone()
            if not recording_row:
                raise ValueError(f"Recording '{name}' not found")

            recording_id = int(recording_row["id"])
            version = self._next_summary_version(conn, recording_id)

            result = conn.execute(
                """
                INSERT INTO summary (recording_id, version, title, tags, summary, prompt_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (recording_id, version, title, tags, summary, prompt_id),
            )

            if title and title.strip():
                conn.execute("UPDATE recording SET label = ? WHERE id = ?", (title.strip(), recording_id))

            conn.commit()
            return DBSummary(
                id=result.lastrowid,
                recording_id=recording_id,
                recording_name=name,
                version=version,
                summary=summary,
                title=title,
                tags=tags,
                prompt_id=prompt_id,
            )
        finally:
            conn.close()

    def get_summaries(self, name: str) -> list[DBSummary]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.recording_id,
                    r.name AS recording_name,
                    s.version,
                    s.title,
                    s.tags,
                    s.summary,
                    s.prompt_id,
                    s.notion_url,
                    s.created_at
                FROM summary s
                JOIN recording r ON r.id = s.recording_id
                WHERE r.name = ?
                ORDER BY s.version DESC
                """,
                (name,),
            ).fetchall()
            return [DBSummary.from_dict(row) for row in rows]
        finally:
            conn.close()

    def get_summary(self, name: str) -> str | None:
        summaries = self.get_summaries(name)
        return summaries[0].summary if summaries else None

    def save_summary(self, name: str, summary: str) -> None:
        self.save_summarization_result(name=name, summary=summary, title="", tags="", prompt_id=None)

    def get_summary_by_id(self, summary_id: int) -> DBSummary | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    s.id,
                    s.recording_id,
                    r.name AS recording_name,
                    s.version,
                    s.title,
                    s.tags,
                    s.summary,
                    s.prompt_id,
                    s.notion_url,
                    s.created_at
                FROM summary s
                JOIN recording r ON r.id = s.recording_id
                WHERE s.id = ?
                """,
                (summary_id,),
            ).fetchone()
            return DBSummary.from_dict(row) if row else None
        finally:
            conn.close()

    def update_summary_metadata(self, summary_id: int, title: str, tags: str) -> DBSummary | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT id, recording_id FROM summary WHERE id = ?", (summary_id,)).fetchone()
            if not row:
                return None

            conn.execute("UPDATE summary SET title = ?, tags = ? WHERE id = ?", (title, tags, summary_id))

            # Keep recording.label aligned to the latest summary title.
            latest = conn.execute(
                "SELECT id, title FROM summary WHERE recording_id = ? ORDER BY version DESC LIMIT 1",
                (row["recording_id"],),
            ).fetchone()
            if latest and int(latest["id"]) == summary_id and title.strip():
                conn.execute("UPDATE recording SET label = ? WHERE id = ?", (title.strip(), row["recording_id"]))

            conn.commit()
            return self.get_summary_by_id(summary_id)
        finally:
            conn.close()

    def update_summary_content(self, summary_id: int, summary: str) -> DBSummary | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT id FROM summary WHERE id = ?", (summary_id,)).fetchone()
            if not row:
                return None

            conn.execute("UPDATE summary SET summary = ? WHERE id = ?", (summary, summary_id))
            conn.commit()
            return self.get_summary_by_id(summary_id)
        finally:
            conn.close()

    def update_title_and_tags(self, name: str, title: str, tags: str) -> None:
        summaries = self.get_summaries(name)
        if not summaries:
            self.save_summarization_result(name=name, summary="", title=title, tags=tags, prompt_id=None)
            return
        self.update_summary_metadata(summaries[0].id, title, tags)

    def get_latest_summaries_map(self) -> dict[str, DBSummary]:
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT
                    s.id,
                    s.recording_id,
                    r.name AS recording_name,
                    s.version,
                    s.title,
                    s.tags,
                    s.summary,
                    s.prompt_id,
                    s.notion_url,
                    s.created_at
                FROM summary s
                JOIN recording r ON r.id = s.recording_id
                JOIN (
                    SELECT recording_id, MAX(version) AS max_version
                    FROM summary
                    GROUP BY recording_id
                ) m ON m.recording_id = s.recording_id AND m.max_version = s.version
                """).fetchall()
            return {row["recording_name"]: DBSummary.from_dict(row) for row in rows}
        finally:
            conn.close()

    def delete_recording(self, name: str) -> bool:
        conn = self._connect()
        try:
            result = conn.execute("DELETE FROM recording WHERE name = ?", (name,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    # ─── Folder operations ────────────────────────────────────────

    def get_recording_folders(self) -> list[str]:
        """Return all distinct folder paths used by recordings, sorted."""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT DISTINCT folder FROM recording ORDER BY folder").fetchall()
            folders = [row["folder"] for row in rows]
            if "/" not in folders:
                folders.insert(0, "/")
            return folders
        finally:
            conn.close()

    def move_recording_to_folder(self, name: str, folder: str) -> bool:
        """Move a recording to a different folder."""
        conn = self._connect()
        try:
            result = conn.execute("UPDATE recording SET folder = ? WHERE name = ?", (folder, name))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def rename_folder(self, old_path: str, new_path: str) -> int:
        """Rename a folder and all its sub-folders. Returns number of updated recordings."""
        conn = self._connect()
        try:
            # Exact match
            result1 = conn.execute(
                "UPDATE recording SET folder = ? WHERE folder = ?",
                (new_path, old_path),
            )
            count = result1.rowcount
            # Sub-folders: old_path + '/' prefix → new_path + '/' prefix
            if not old_path.endswith("/"):
                old_prefix = old_path + "/"
            else:
                old_prefix = old_path
            if not new_path.endswith("/"):
                new_prefix = new_path + "/"
            else:
                new_prefix = new_path
            rows = conn.execute(
                "SELECT id, folder FROM recording WHERE folder LIKE ?",
                (old_prefix + "%",),
            ).fetchall()
            for row in rows:
                updated_folder = new_prefix + row["folder"][len(old_prefix) :]
                conn.execute("UPDATE recording SET folder = ? WHERE id = ?", (updated_folder, row["id"]))
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def delete_folder(self, folder_path: str, move_to: str = "/") -> int:
        """Move all recordings from a folder (and sub-folders) to *move_to*. Returns count."""
        conn = self._connect()
        try:
            result1 = conn.execute(
                "UPDATE recording SET folder = ? WHERE folder = ?",
                (move_to, folder_path),
            )
            count = result1.rowcount
            prefix = folder_path if folder_path.endswith("/") else folder_path + "/"
            result2 = conn.execute(
                "UPDATE recording SET folder = ? WHERE folder LIKE ?",
                (move_to, prefix + "%"),
            )
            count += result2.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def bulk_move_recordings_to_folder(self, names: list[str], folder: str) -> int:
        """Move multiple recordings to a folder. Returns number updated."""
        conn = self._connect()
        try:
            count = 0
            for name in names:
                result = conn.execute("UPDATE recording SET folder = ? WHERE name = ?", (folder, name))
                count += result.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def save_notion_url(self, summary_id_or_name: int | str, url: str) -> None:
        conn = self._connect()
        try:
            if isinstance(summary_id_or_name, int):
                conn.execute("UPDATE summary SET notion_url = ? WHERE id = ?", (url, summary_id_or_name))
            else:
                row = conn.execute(
                    """
                    SELECT s.id
                    FROM summary s
                    JOIN recording r ON r.id = s.recording_id
                    WHERE r.name = ?
                    ORDER BY s.version DESC
                    LIMIT 1
                    """,
                    (summary_id_or_name,),
                ).fetchone()
                if row:
                    conn.execute("UPDATE summary SET notion_url = ? WHERE id = ?", (url, row["id"]))
                else:
                    recording = conn.execute(
                        "SELECT id FROM recording WHERE name = ?", (summary_id_or_name,)
                    ).fetchone()
                    if recording:
                        version = self._next_summary_version(conn, int(recording["id"]))
                        conn.execute(
                            """
                            INSERT INTO summary (recording_id, version, title, tags, summary, prompt_id, notion_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (int(recording["id"]), version, "", "", "", None, url),
                        )
            conn.commit()
        finally:
            conn.close()

    # ─── Task CRUD ───────────────────────────────────────────────

    def insert_task(self, task: DBTask) -> DBTask:
        conn = self._connect()
        try:
            result = conn.execute(
                """
                INSERT INTO task (summary_id, parent_task_id, title, description, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task.summary_id, task.parent_task_id, task.title, task.description, task.status),
            )
            conn.commit()
            task.id = result.lastrowid
            return task
        finally:
            conn.close()

    def insert_tasks(self, tasks: list[DBTask]) -> list[DBTask]:
        conn = self._connect()
        try:
            created = []
            for task in tasks:
                result = conn.execute(
                    """
                    INSERT INTO task (summary_id, parent_task_id, title, description, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (task.summary_id, task.parent_task_id, task.title, task.description, task.status),
                )
                task.id = result.lastrowid

                # Insert subtasks with the parent id set
                for sub in task.subtasks:
                    sub.parent_task_id = task.id
                    sub.summary_id = task.summary_id
                    sub_result = conn.execute(
                        """
                        INSERT INTO task (summary_id, parent_task_id, title, description, status)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (sub.summary_id, sub.parent_task_id, sub.title, sub.description, sub.status),
                    )
                    sub.id = sub_result.lastrowid

                created.append(task)
            conn.commit()
            return created
        finally:
            conn.close()

    def get_tasks_by_summary(self, summary_id: int) -> list[DBTask]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM task WHERE summary_id = ? ORDER BY created_at ASC, id ASC",
                (summary_id,),
            ).fetchall()

            task_map: dict[int, DBTask] = {}
            top_level: list[DBTask] = []

            for row in rows:
                task = DBTask.from_dict(row)
                task_map[task.id] = task

            for task in task_map.values():
                if task.parent_task_id and task.parent_task_id in task_map:
                    task_map[task.parent_task_id].subtasks.append(task)
                else:
                    top_level.append(task)

            return top_level
        finally:
            conn.close()

    def get_task_by_id(self, task_id: int) -> DBTask | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
            return DBTask.from_dict(row) if row else None
        finally:
            conn.close()

    def update_task(
        self, task_id: int, title: str | None = None, description: str | None = None, status: str | None = None
    ) -> DBTask | None:
        conn = self._connect()
        try:
            existing = conn.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
            if not existing:
                return None

            new_title = title if title is not None else existing["title"]
            new_description = description if description is not None else existing["description"]
            new_status = status if status is not None else existing["status"]

            conn.execute(
                "UPDATE task SET title = ?, description = ?, status = ? WHERE id = ?",
                (new_title, new_description, new_status, task_id),
            )
            conn.commit()
            return self.get_task_by_id(task_id)
        finally:
            conn.close()

    def delete_task(self, task_id: int) -> bool:
        conn = self._connect()
        try:
            result = conn.execute("DELETE FROM task WHERE id = ?", (task_id,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def delete_tasks_by_summary(self, summary_id: int) -> int:
        conn = self._connect()
        try:
            result = conn.execute("DELETE FROM task WHERE summary_id = ?", (summary_id,))
            conn.commit()
            return result.rowcount
        finally:
            conn.close()

    def has_tasks_for_summary(self, summary_id: int) -> bool:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM task WHERE summary_id = ?", (summary_id,)).fetchone()
            return row["cnt"] > 0
        finally:
            conn.close()

    # ─── Calendar CRUD ────────────────────────────────────────────

    def _ensure_calendar_tables(self) -> None:
        """Create calendar tables if they don't exist (migration-safe)."""
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS shared_calendar (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                  TEXT    NOT NULL,
                    ical_url              TEXT    NOT NULL,
                    color                 TEXT    NOT NULL DEFAULT '#0d6efd',
                    is_enabled            INTEGER NOT NULL DEFAULT 1,
                    sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
                    last_synced_at        TEXT    DEFAULT NULL,
                    last_error            TEXT    DEFAULT NULL,
                    created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS calendar_event (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider           TEXT    NOT NULL DEFAULT 'local',
                    external_id        TEXT    DEFAULT NULL,
                    shared_calendar_id INTEGER DEFAULT NULL,
                    title              TEXT    NOT NULL,
                    description        TEXT    DEFAULT NULL,
                    start_at           TEXT    NOT NULL,
                    end_at             TEXT    NOT NULL,
                    is_all_day         INTEGER NOT NULL DEFAULT 0,
                    location           TEXT    DEFAULT NULL,
                    meeting_url        TEXT    DEFAULT NULL,
                    status             TEXT    NOT NULL DEFAULT 'confirmed',
                    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
                    UNIQUE (provider, external_id),
                    FOREIGN KEY (shared_calendar_id) REFERENCES shared_calendar (id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_calendar_event_start ON calendar_event (start_at);

                CREATE TABLE IF NOT EXISTS recording_event_link (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    recording_id INTEGER NOT NULL,
                    event_id     INTEGER NOT NULL,
                    link_source  TEXT    NOT NULL DEFAULT 'manual',
                    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (recording_id) REFERENCES recording (id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES calendar_event (id) ON DELETE CASCADE,
                    UNIQUE (recording_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS idx_recording_event_link_recording ON recording_event_link (recording_id);
                CREATE INDEX IF NOT EXISTS idx_recording_event_link_event ON recording_event_link (event_id);

                CREATE TABLE IF NOT EXISTS daily_recap (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    date         TEXT    NOT NULL UNIQUE,
                    title        TEXT    DEFAULT NULL,
                    highlights   TEXT    DEFAULT NULL,
                    recap        TEXT    DEFAULT NULL,
                    action_items TEXT    DEFAULT NULL,
                    blockers     TEXT    DEFAULT NULL,
                    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_daily_recap_date ON daily_recap (date);
            """)
            # Migration: add shared_calendar_id column if missing on existing DB
            try:
                conn.execute("SELECT shared_calendar_id FROM calendar_event LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE calendar_event ADD COLUMN shared_calendar_id INTEGER DEFAULT NULL")
            # Migration: add status column if missing on existing DB
            try:
                conn.execute("SELECT status FROM calendar_event LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE calendar_event ADD COLUMN status TEXT NOT NULL DEFAULT 'confirmed'")
            conn.commit()
        finally:
            conn.close()

    def insert_calendar_event(self, event: DBCalendarEvent) -> DBCalendarEvent:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            result = conn.execute(
                """
                INSERT INTO calendar_event (provider, external_id, title, description, start_at, end_at,
                                            is_all_day, location, meeting_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.provider,
                    event.external_id,
                    event.title,
                    event.description,
                    event.start_at,
                    event.end_at,
                    int(event.is_all_day),
                    event.location,
                    event.meeting_url,
                ),
            )
            conn.commit()
            event.id = result.lastrowid
            return event
        finally:
            conn.close()

    def update_calendar_event(
        self,
        event_id: int,
        title: str | None = None,
        description: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        is_all_day: bool | None = None,
        location: str | None = None,
        meeting_url: str | None = None,
    ) -> DBCalendarEvent | None:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            existing = conn.execute("SELECT * FROM calendar_event WHERE id = ?", (event_id,)).fetchone()
            if not existing:
                return None
            new_title = title if title is not None else existing["title"]
            new_desc = description if description is not None else existing["description"]
            new_start = start_at if start_at is not None else existing["start_at"]
            new_end = end_at if end_at is not None else existing["end_at"]
            new_all_day = int(is_all_day) if is_all_day is not None else existing["is_all_day"]
            new_location = location if location is not None else existing["location"]
            new_meeting_url = meeting_url if meeting_url is not None else existing["meeting_url"]
            conn.execute(
                """
                UPDATE calendar_event SET title=?, description=?, start_at=?, end_at=?,
                       is_all_day=?, location=?, meeting_url=?
                WHERE id=?
                """,
                (new_title, new_desc, new_start, new_end, new_all_day, new_location, new_meeting_url, event_id),
            )
            conn.commit()
            return self.get_calendar_event_by_id(event_id)
        finally:
            conn.close()

    def delete_calendar_event(self, event_id: int) -> bool:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            result = conn.execute("DELETE FROM calendar_event WHERE id = ?", (event_id,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def get_calendar_event_by_id(self, event_id: int) -> DBCalendarEvent | None:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM calendar_event WHERE id = ?", (event_id,)).fetchone()
            if not row:
                return None
            event = DBCalendarEvent.from_dict(row)
            event.linked_recordings = self._get_linked_recordings(conn, event_id)
            return event
        finally:
            conn.close()

    def get_calendar_events_for_day(self, date_str: str) -> list[DBCalendarEvent]:
        """Get all events that overlap with the given day (YYYY-MM-DD)."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            day_start = f"{date_str} 00:00:00"
            day_end = f"{date_str} 23:59:59"
            rows = conn.execute(
                """
                SELECT ce.*, sc.color AS calendar_color
                FROM calendar_event ce
                LEFT JOIN shared_calendar sc ON sc.id = ce.shared_calendar_id
                WHERE ce.start_at <= ? AND ce.end_at >= ?
                ORDER BY ce.start_at ASC
                """,
                (day_end, day_start),
            ).fetchall()
            events = []
            for row in rows:
                event = DBCalendarEvent.from_dict(row)
                event.calendar_color = row["calendar_color"] if "calendar_color" in row.keys() else None
                event.linked_recordings = self._get_linked_recordings(conn, event.id)
                events.append(event)
            return events
        finally:
            conn.close()

    def get_calendar_events_for_month(self, year: int, month: int) -> list[DBCalendarEvent]:
        """Get all events in a given month."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            month_start = f"{year:04d}-{month:02d}-01 00:00:00"
            if month == 12:
                month_end = f"{year + 1:04d}-01-01 00:00:00"
            else:
                month_end = f"{year:04d}-{month + 1:02d}-01 00:00:00"
            rows = conn.execute(
                """
                SELECT ce.*, sc.color AS calendar_color
                FROM calendar_event ce
                LEFT JOIN shared_calendar sc ON sc.id = ce.shared_calendar_id
                WHERE ce.start_at < ? AND ce.end_at >= ?
                ORDER BY ce.start_at ASC
                """,
                (month_end, month_start),
            ).fetchall()
            events = []
            for row in rows:
                event = DBCalendarEvent.from_dict(row)
                event.calendar_color = row["calendar_color"] if "calendar_color" in row.keys() else None
                event.linked_recordings = self._get_linked_recordings(conn, event.id)
                events.append(event)
            return events
        finally:
            conn.close()

    def get_calendar_events_for_range(self, start_date: str, end_date: str) -> list[DBCalendarEvent]:
        """Get all events that overlap with the given date range (YYYY-MM-DD)."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            range_start = f"{start_date} 00:00:00"
            range_end = f"{end_date} 23:59:59"
            rows = conn.execute(
                """
                SELECT ce.*, sc.color AS calendar_color, sc.name AS calendar_name
                FROM calendar_event ce
                LEFT JOIN shared_calendar sc ON sc.id = ce.shared_calendar_id
                WHERE ce.start_at <= ? AND ce.end_at >= ?
                ORDER BY ce.start_at ASC
                """,
                (range_end, range_start),
            ).fetchall()
            events = []
            for row in rows:
                event = DBCalendarEvent.from_dict(row)
                event.calendar_color = row["calendar_color"] if "calendar_color" in row.keys() else None
                event.calendar_name = row["calendar_name"] if "calendar_name" in row.keys() else None
                event.linked_recordings = self._get_linked_recordings(conn, event.id)
                events.append(event)
            return events
        finally:
            conn.close()

    def _get_linked_recordings(self, conn, event_id: int) -> list[dict]:
        rows = conn.execute(
            """
            SELECT r.id as recording_id, r.name, r.label, r.transcript,
                   rel.link_source
            FROM recording_event_link rel
            JOIN recording r ON r.id = rel.recording_id
            WHERE rel.event_id = ?
            ORDER BY r.name ASC
            """,
            (event_id,),
        ).fetchall()
        result = []
        for row in rows:
            # Check latest summary
            summary_row = conn.execute(
                """
                SELECT id, title, tags, summary FROM summary
                WHERE recording_id = ? ORDER BY version DESC LIMIT 1
                """,
                (row["recording_id"],),
            ).fetchone()
            result.append(
                {
                    "recording_id": row["recording_id"],
                    "name": row["name"],
                    "label": row["label"],
                    "link_source": row["link_source"],
                    "has_transcript": row["transcript"] is not None and len(row["transcript"]) > 0,
                    "has_summary": summary_row is not None,
                    "summary_id": summary_row["id"] if summary_row else None,
                    "summary_title": summary_row["title"] if summary_row else None,
                    "summary_tags": summary_row["tags"].split(",") if summary_row and summary_row["tags"] else [],
                    "summary_text": summary_row["summary"] if summary_row else None,
                }
            )
        return result

    def link_recording_to_event(self, recording_id: int, event_id: int, link_source: str = "manual") -> bool:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO recording_event_link (recording_id, event_id, link_source) VALUES (?, ?, ?)",
                (recording_id, event_id, link_source),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def unlink_recording_from_event(self, recording_id: int, event_id: int) -> bool:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            result = conn.execute(
                "DELETE FROM recording_event_link WHERE recording_id = ? AND event_id = ?",
                (recording_id, event_id),
            )
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def get_events_for_recording(self, recording_id: int) -> list[DBCalendarEvent]:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT ce.* FROM calendar_event ce
                JOIN recording_event_link rel ON rel.event_id = ce.id
                WHERE rel.recording_id = ?
                ORDER BY ce.start_at ASC
                """,
                (recording_id,),
            ).fetchall()
            return [DBCalendarEvent.from_dict(row) for row in rows]
        finally:
            conn.close()

    def get_recordings_for_day(self, date_str: str) -> list[dict]:
        """Get recordings whose recorded_at or name-parsed date matches the given day."""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT id, name, label, duration, recorded_at, transcript FROM recording").fetchall()
            result = []
            for row in rows:
                if row["recorded_at"]:
                    rec_date = row["recorded_at"][:10]
                else:
                    rec_date = self._parse_recording_date_from_name(row["name"])
                if rec_date == date_str:
                    summary_row = conn.execute(
                        "SELECT title, tags FROM summary WHERE recording_id = ? ORDER BY version DESC LIMIT 1",
                        (row["id"],),
                    ).fetchone()
                    result.append(
                        {
                            "recording_id": row["id"],
                            "name": row["name"],
                            "label": row["label"],
                            "duration": row["duration"],
                            "has_transcript": row["transcript"] is not None and len(row["transcript"]) > 0,
                            "has_summary": summary_row is not None,
                            "summary_title": summary_row["title"] if summary_row else None,
                            "summary_tags": (
                                summary_row["tags"].split(",") if summary_row and summary_row["tags"] else []
                            ),
                        }
                    )
            return result
        finally:
            conn.close()

    @staticmethod
    def _parse_recording_date_from_name(name: str) -> str | None:
        """Parse recording name like '2026Apr01-152300-Rec13' → '2026-04-01'."""
        from datetime import datetime as dt

        try:
            parts = name.split("-")
            if len(parts) >= 2:
                dt_str = f"{parts[0]}-{parts[1]}"
                parsed = dt.strptime(dt_str, "%Y%b%d-%H%M%S")
                return parsed.strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            pass
        return None

    # ─── Daily Recap CRUD ──────────────────────────────────────────

    def save_daily_recap(self, recap: DBDailyRecap) -> DBDailyRecap:
        """Insert or replace the daily recap for a given date."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            highlights_json = json.dumps(recap.highlights) if recap.highlights else None
            action_items_json = json.dumps(recap.action_items) if recap.action_items else None
            blockers_json = json.dumps(recap.blockers) if recap.blockers else None

            conn.execute(
                """
                INSERT INTO daily_recap (date, title, highlights, recap, action_items, blockers, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    title = excluded.title,
                    highlights = excluded.highlights,
                    recap = excluded.recap,
                    action_items = excluded.action_items,
                    blockers = excluded.blockers,
                    updated_at = datetime('now')
                """,
                (recap.date, recap.title, highlights_json, recap.recap, action_items_json, blockers_json),
            )
            conn.commit()
            return self.get_daily_recap(recap.date)
        finally:
            conn.close()

    def get_daily_recap(self, date_str: str) -> DBDailyRecap | None:
        """Get the stored daily recap for a given date."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM daily_recap WHERE date = ?", (date_str,)).fetchone()
            if not row:
                return None
            return DBDailyRecap.from_dict(row)
        finally:
            conn.close()

    def delete_daily_recap(self, date_str: str) -> bool:
        """Delete the daily recap for a given date."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            result = conn.execute("DELETE FROM daily_recap WHERE date = ?", (date_str,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def get_daily_recaps_for_month(self, year: int, month: int) -> list[str]:
        """Return list of date strings that have stored recaps for a given month."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            month_start = f"{year:04d}-{month:02d}-01"
            if month == 12:
                month_end = f"{year + 1:04d}-01-01"
            else:
                month_end = f"{year:04d}-{month + 1:02d}-01"
            rows = conn.execute(
                "SELECT date FROM daily_recap WHERE date >= ? AND date < ? ORDER BY date",
                (month_start, month_end),
            ).fetchall()
            return [row["date"] for row in rows]
        finally:
            conn.close()

    # ─── Shared Calendar CRUD ─────────────────────────────────────

    def get_shared_calendars(self) -> list[DBSharedCalendar]:
        """Get all shared calendars with event counts."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT sc.*,
                       (SELECT COUNT(*) FROM calendar_event ce WHERE ce.shared_calendar_id = sc.id) AS event_count
                FROM shared_calendar sc
                ORDER BY sc.name ASC
                """).fetchall()
            calendars = []
            for row in rows:
                cal = DBSharedCalendar.from_dict(row)
                cal.event_count = row["event_count"]
                calendars.append(cal)
            return calendars
        finally:
            conn.close()

    def get_shared_calendar_by_id(self, calendar_id: int) -> DBSharedCalendar | None:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM shared_calendar WHERE id = ?", (calendar_id,)).fetchone()
            return DBSharedCalendar.from_dict(row) if row else None
        finally:
            conn.close()

    def insert_shared_calendar(self, cal: DBSharedCalendar) -> DBSharedCalendar:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            result = conn.execute(
                """
                INSERT INTO shared_calendar (name, ical_url, color, is_enabled, sync_interval_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cal.name, cal.ical_url, cal.color, int(cal.is_enabled), cal.sync_interval_minutes),
            )
            conn.commit()
            cal.id = result.lastrowid
            return cal
        finally:
            conn.close()

    def update_shared_calendar(self, calendar_id: int, **kwargs) -> DBSharedCalendar | None:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            existing = conn.execute("SELECT * FROM shared_calendar WHERE id = ?", (calendar_id,)).fetchone()
            if not existing:
                return None
            name = kwargs.get("name", existing["name"])
            ical_url = kwargs.get("ical_url", existing["ical_url"])
            color = kwargs.get("color", existing["color"])
            is_enabled = int(kwargs["is_enabled"]) if "is_enabled" in kwargs else existing["is_enabled"]
            sync_interval = kwargs.get("sync_interval_minutes", existing["sync_interval_minutes"])
            conn.execute(
                """
                UPDATE shared_calendar SET name=?, ical_url=?, color=?, is_enabled=?, sync_interval_minutes=?
                WHERE id=?
                """,
                (name, ical_url, color, is_enabled, sync_interval, calendar_id),
            )
            conn.commit()
            return self.get_shared_calendar_by_id(calendar_id)
        finally:
            conn.close()

    def delete_shared_calendar(self, calendar_id: int) -> bool:
        """Delete a shared calendar and all its synced events."""
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            conn.execute("DELETE FROM calendar_event WHERE shared_calendar_id = ?", (calendar_id,))
            result = conn.execute("DELETE FROM shared_calendar WHERE id = ?", (calendar_id,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def sync_shared_calendar_events(
        self,
        calendar_id: int,
        provider_name: str,
        events: list[DBCalendarEvent],
    ) -> dict:
        """
        Upsert events from an iCal feed. Deletes stale events no longer in the feed.
        """
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            incoming_eids = {ev.external_id for ev in events if ev.external_id}

            existing_rows = conn.execute(
                "SELECT id, external_id FROM calendar_event WHERE shared_calendar_id = ?",
                (calendar_id,),
            ).fetchall()

            existing_map = {row["external_id"]: row["id"] for row in existing_rows}

            inserted = 0
            updated = 0

            for ev in events:
                if ev.external_id in existing_map:
                    conn.execute(
                        """
                        UPDATE calendar_event
                        SET title=?, description=?, start_at=?, end_at=?, is_all_day=?,
                            location=?, meeting_url=?, status=?
                        WHERE id=?
                        """,
                        (
                            ev.title,
                            ev.description,
                            ev.start_at,
                            ev.end_at,
                            int(ev.is_all_day),
                            ev.location,
                            ev.meeting_url,
                            ev.status,
                            existing_map[ev.external_id],
                        ),
                    )
                    updated += 1
                else:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO calendar_event
                            (provider, external_id, shared_calendar_id, title, description,
                             start_at, end_at, is_all_day, location, meeting_url, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            provider_name,
                            ev.external_id,
                            calendar_id,
                            ev.title,
                            ev.description,
                            ev.start_at,
                            ev.end_at,
                            int(ev.is_all_day),
                            ev.location,
                            ev.meeting_url,
                            ev.status,
                        ),
                    )
                    inserted += 1

            stale_eids = set(existing_map.keys()) - incoming_eids
            deleted = 0
            for eid in stale_eids:
                conn.execute("DELETE FROM calendar_event WHERE id = ?", (existing_map[eid],))
                deleted += 1

            conn.execute(
                "UPDATE shared_calendar SET last_synced_at = datetime('now'), last_error = NULL WHERE id = ?",
                (calendar_id,),
            )
            conn.commit()

            return {"inserted": inserted, "updated": updated, "deleted": deleted}
        finally:
            conn.close()

    def set_shared_calendar_error(self, calendar_id: int, error: str) -> None:
        self._ensure_calendar_tables()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE shared_calendar SET last_error = ? WHERE id = ?",
                (error, calendar_id),
            )
            conn.commit()
        finally:
            conn.close()
