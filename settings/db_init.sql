CREATE TABLE IF NOT EXISTS recording
(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    label           TEXT    NOT NULL,
    duration        INTEGER NOT NULL,
    file_extension  TEXT    NOT NULL DEFAULT 'hda',
    recorded_at     TEXT    DEFAULT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    transcript      TEXT    DEFAULT NULL,
    folder          TEXT    NOT NULL DEFAULT '/'
);

CREATE TABLE IF NOT EXISTS summary
(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER NOT NULL,
    version      INTEGER NOT NULL,
    title        TEXT    DEFAULT NULL,
    tags         TEXT    DEFAULT NULL,
    summary      TEXT    NOT NULL,
    prompt_id    TEXT    DEFAULT NULL,
    notion_url   TEXT    DEFAULT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (recording_id) REFERENCES recording (id) ON DELETE CASCADE,
    UNIQUE (recording_id, version)
);

CREATE INDEX IF NOT EXISTS idx_summary_recording_id ON summary (recording_id);

CREATE TABLE IF NOT EXISTS task
(
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id     INTEGER NOT NULL,
    parent_task_id INTEGER DEFAULT NULL,
    title          TEXT    NOT NULL,
    description    TEXT    DEFAULT NULL,
    status         TEXT    NOT NULL DEFAULT 'open',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (summary_id) REFERENCES summary (id) ON DELETE CASCADE,
    FOREIGN KEY (parent_task_id) REFERENCES task (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_summary_id ON task (summary_id);
CREATE INDEX IF NOT EXISTS idx_task_parent_task_id ON task (parent_task_id);

CREATE TABLE IF NOT EXISTS shared_calendar
(
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

CREATE TABLE IF NOT EXISTS calendar_event
(
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    provider            TEXT    NOT NULL DEFAULT 'local',
    external_id         TEXT    DEFAULT NULL,
    shared_calendar_id  INTEGER DEFAULT NULL,
    title               TEXT    NOT NULL,
    description         TEXT    DEFAULT NULL,
    start_at            TEXT    NOT NULL,
    end_at              TEXT    NOT NULL,
    is_all_day          INTEGER NOT NULL DEFAULT 0,
    location            TEXT    DEFAULT NULL,
    meeting_url         TEXT    DEFAULT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (provider, external_id),
    FOREIGN KEY (shared_calendar_id) REFERENCES shared_calendar (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_start ON calendar_event (start_at);
CREATE INDEX IF NOT EXISTS idx_calendar_event_provider ON calendar_event (provider);

CREATE TABLE IF NOT EXISTS recording_event_link
(
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

CREATE TABLE IF NOT EXISTS daily_recap
(
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

