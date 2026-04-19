# AgenDino Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gemini transcription with Deepgram Nova, replace Notion with Obsidian export, add cost tracking, stats dashboard, markdown prompt support, and a model comparison lab.

**Architecture:** Six features layered bottom-up: database schema first (cost tracking + comparison tables), then services (Deepgram, Obsidian, ModelRegistry), then controllers/repository wiring, then UI pages (stats, compare), and finally the small prompt-loader change. Each task is self-contained and produces a commit.

**Tech Stack:** Python 3.14, FastAPI, SQLite, Jinja2/Bootstrap, Deepgram SDK, Google Gemini SDK, Chart.js

---

## Task 1: Database Schema — Cost Tracking + Comparison Tables

**Files:**
- Modify: `settings/db_init.sql`
- Modify: `src/repositories/SqliteDBRepository.py:34-54` (migration method)

- [ ] **Step 1: Add cost_tracking table to db_init.sql**

Append to end of `settings/db_init.sql`:

```sql
CREATE TABLE IF NOT EXISTS cost_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER REFERENCES recording(id) ON DELETE CASCADE,
    operation TEXT NOT NULL,
    engine TEXT NOT NULL,
    model TEXT,
    input_units REAL,
    output_units REAL,
    cost_usd REAL NOT NULL,
    estimated INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cost_tracking_recording ON cost_tracking (recording_id);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_operation ON cost_tracking (operation);
```

- [ ] **Step 2: Add comparison tables to db_init.sql**

Append to end of `settings/db_init.sql`:

```sql
CREATE TABLE IF NOT EXISTS comparison_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER REFERENCES recording(id) ON DELETE CASCADE,
    run_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comparison_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    model TEXT,
    system_prompt_id TEXT,
    output_text TEXT NOT NULL,
    cost_usd REAL DEFAULT 0.0,
    processing_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_comparison_result_run ON comparison_result (run_id);

CREATE TABLE IF NOT EXISTS comparison_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
    segment_index INTEGER,
    preferred_result_id INTEGER REFERENCES comparison_result(id),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_comparison_feedback_run ON comparison_feedback (run_id);
```

- [ ] **Step 3: Add migration for existing databases in SqliteDBRepository**

In `src/repositories/SqliteDBRepository.py`, add a new method `_ensure_cost_tracking_tables` and call it from `__init__` after `_ensure_recording_columns()`:

```python
# In __init__, after self._ensure_recording_columns():
self._ensure_cost_tracking_tables()

def _ensure_cost_tracking_tables(self) -> None:
    """Migration: create cost_tracking and comparison tables if missing."""
    conn = self._connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cost_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id INTEGER REFERENCES recording(id) ON DELETE CASCADE,
                operation TEXT NOT NULL,
                engine TEXT NOT NULL,
                model TEXT,
                input_units REAL,
                output_units REAL,
                cost_usd REAL NOT NULL,
                estimated INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cost_tracking_recording ON cost_tracking (recording_id);
            CREATE INDEX IF NOT EXISTS idx_cost_tracking_operation ON cost_tracking (operation);

            CREATE TABLE IF NOT EXISTS comparison_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id INTEGER REFERENCES recording(id) ON DELETE CASCADE,
                run_type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS comparison_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
                engine TEXT NOT NULL,
                model TEXT,
                system_prompt_id TEXT,
                output_text TEXT NOT NULL,
                cost_usd REAL DEFAULT 0.0,
                processing_time_ms INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_comparison_result_run ON comparison_result (run_id);
            CREATE TABLE IF NOT EXISTS comparison_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
                segment_index INTEGER,
                preferred_result_id INTEGER REFERENCES comparison_result(id),
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_comparison_feedback_run ON comparison_feedback (run_id);
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Verify the app starts and existing DB migrates**

Run: `cd src && python -c "from repositories.SqliteDBRepository import SqliteDBRepository; import os; r = SqliteDBRepository('agendino.db', os.path.join(os.path.dirname(os.path.abspath('.')), 'settings'), os.path.join(os.path.dirname(os.path.abspath('.')), 'settings/db_init.sql')); print('OK')"`

Expected: `OK` — no crash, tables created silently.

- [ ] **Step 5: Commit**

```bash
git add settings/db_init.sql src/repositories/SqliteDBRepository.py
git commit -m "feat: add cost_tracking and comparison tables to schema"
```

---

## Task 2: CostMetadata DTO + CostTrackingRepository

**Files:**
- Create: `src/models/dto/CostMetadata.py`
- Create: `src/repositories/CostTrackingRepository.py`

- [ ] **Step 1: Create CostMetadata dataclass**

Create `src/models/dto/CostMetadata.py`:

```python
from dataclasses import dataclass


@dataclass
class CostMetadata:
    operation: str      # transcription, summarization, task_generation, daily_recap, rag_query, embedding, comparison
    engine: str         # deepgram, whisper, gemini
    model: str          # specific model identifier
    input_units: float  # audio minutes (transcription) or input tokens (LLM)
    output_units: float # output tokens (0 for transcription)
    cost_usd: float
```

- [ ] **Step 2: Create CostTrackingRepository**

Create `src/repositories/CostTrackingRepository.py`:

```python
import sqlite3

from models.dto.CostMetadata import CostMetadata


class CostTrackingRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save(self, recording_id: int | None, cost: CostMetadata, estimated: bool = False) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO cost_tracking
                   (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recording_id, cost.operation, cost.engine, cost.model,
                 cost.input_units, cost.output_units, cost.cost_usd, 1 if estimated else 0),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_by_recording(self, recording_id: int) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cost_tracking WHERE recording_id = ? ORDER BY created_at",
                (recording_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_by_date_range(self, start: str, end: str) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cost_tracking WHERE created_at >= ? AND created_at <= ? ORDER BY created_at",
                (start, end),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_totals(self) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT
                     COUNT(*) as total_operations,
                     COALESCE(SUM(cost_usd), 0) as total_cost,
                     COALESCE(SUM(CASE WHEN operation='transcription' THEN cost_usd ELSE 0 END), 0) as transcription_cost,
                     COALESCE(SUM(CASE WHEN operation='summarization' THEN cost_usd ELSE 0 END), 0) as summarization_cost,
                     COALESCE(SUM(CASE WHEN operation='task_generation' THEN cost_usd ELSE 0 END), 0) as task_generation_cost,
                     COALESCE(SUM(CASE WHEN operation='comparison' THEN cost_usd ELSE 0 END), 0) as comparison_cost
                """
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def get_by_engine(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT engine, operation,
                     COUNT(*) as count,
                     COALESCE(SUM(cost_usd), 0) as total_cost
                   FROM cost_tracking
                   GROUP BY engine, operation
                   ORDER BY engine, operation"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_daily_totals(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT DATE(created_at) as date,
                     COALESCE(SUM(cost_usd), 0) as total_cost,
                     COUNT(*) as operations
                   FROM cost_tracking
                   GROUP BY DATE(created_at)
                   ORDER BY date"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_per_recording_costs(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT
                     r.id as recording_id, r.name, r.folder,
                     MIN(ct.created_at) as first_cost_at,
                     COALESCE(SUM(CASE WHEN ct.operation='transcription' THEN ct.cost_usd ELSE 0 END), 0) as transcription_cost,
                     COALESCE(SUM(CASE WHEN ct.operation='summarization' THEN ct.cost_usd ELSE 0 END), 0) as summarization_cost,
                     COALESCE(SUM(ct.cost_usd), 0) as total_cost,
                     MAX(ct.estimated) as has_estimates
                   FROM recording r
                   JOIN cost_tracking ct ON ct.recording_id = r.id
                   GROUP BY r.id
                   ORDER BY total_cost DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_usage_counts(self) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT
                     COUNT(DISTINCT CASE WHEN operation='transcription' THEN recording_id END) as transcriptions,
                     COUNT(DISTINCT CASE WHEN operation='summarization' THEN recording_id END) as summarizations,
                     COUNT(DISTINCT CASE WHEN operation='task_generation' THEN recording_id END) as task_generations,
                     COUNT(DISTINCT CASE WHEN operation='rag_query' THEN id END) as rag_queries,
                     COUNT(DISTINCT CASE WHEN operation='comparison' THEN id END) as comparisons
                   FROM cost_tracking"""
            ).fetchone()
            return dict(row)
        finally:
            conn.close()
```

- [ ] **Step 3: Commit**

```bash
git add src/models/dto/CostMetadata.py src/repositories/CostTrackingRepository.py
git commit -m "feat: add CostMetadata DTO and CostTrackingRepository"
```

---

## Task 3: Deepgram Transcription Service

**Files:**
- Create: `src/services/DeepgramTranscriptionService.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install deepgram-sdk**

Run: `cd /c/Users/junio/GitHub/agendino2 && .venv/Scripts/pip install deepgram-sdk`

Then add `deepgram-sdk` to `requirements.txt` after `faster-whisper`.

- [ ] **Step 2: Create DeepgramTranscriptionService**

Create `src/services/DeepgramTranscriptionService.py`:

```python
import logging
from pathlib import Path

from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from models.dto.CostMetadata import CostMetadata

logger = logging.getLogger(__name__)

# Deepgram Nova pay-as-you-go rate per minute
DEFAULT_RATE_PER_MINUTE = 0.0043


class DeepgramTranscriptionService:
    def __init__(self, api_key: str, rate_per_minute: float = DEFAULT_RATE_PER_MINUTE):
        self._client = DeepgramClient(api_key)
        self._rate_per_minute = rate_per_minute

    def transcribe(self, audio_path: str, mime_type: str = "audio/mpeg") -> tuple[str, CostMetadata]:
        """Transcribe audio with Deepgram Nova. Returns (transcript, cost_metadata)."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing '%s' with Deepgram Nova...", path.name)

        with open(path, "rb") as f:
            buffer_data = f.read()

        payload: FileSource = {"buffer": buffer_data}

        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
            diarize=True,
            language="multi",
            punctuate=True,
            utterances=True,
        )

        response = self._client.listen.rest.v("1").transcribe_file(payload, options)
        result = response.results

        # Extract duration from metadata
        duration_seconds = result.metadata.duration if result.metadata else 0
        audio_minutes = duration_seconds / 60.0

        # Format transcript from utterances (includes speaker labels + timestamps)
        transcript = self._format_utterances(result)

        cost = CostMetadata(
            operation="transcription",
            engine="deepgram",
            model="nova-3",
            input_units=audio_minutes,
            output_units=0,
            cost_usd=round(audio_minutes * self._rate_per_minute, 6),
        )

        logger.info(
            "Deepgram transcription complete: %.1f minutes, $%.4f",
            audio_minutes, cost.cost_usd,
        )
        return transcript, cost

    @staticmethod
    def _format_utterances(result) -> str:
        """Format Deepgram response into [MM:SS] Speaker N: text lines."""
        lines = []

        # Use utterances if available (grouped by speaker turn)
        if result.utterances:
            for utt in result.utterances:
                ts = DeepgramTranscriptionService._format_timestamp(utt.start)
                speaker = utt.speaker + 1  # Deepgram is 0-indexed
                text = utt.transcript.strip()
                if text:
                    lines.append(f"[{ts}] Speaker {speaker}: {text}")
        else:
            # Fallback: use channels/alternatives
            for channel in result.channels:
                for alt in channel.alternatives:
                    if alt.transcript.strip():
                        lines.append(alt.transcript.strip())

        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"
```

- [ ] **Step 3: Commit**

```bash
git add src/services/DeepgramTranscriptionService.py requirements.txt
git commit -m "feat: add DeepgramTranscriptionService with Nova-3 + diarization"
```

---

## Task 4: Obsidian Export Service

**Files:**
- Create: `src/services/ObsidianExportService.py`

- [ ] **Step 1: Create ObsidianExportService**

Create `src/services/ObsidianExportService.py`:

```python
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class ObsidianExportService:
    def __init__(self, vault_path: str):
        self._vault_path = Path(vault_path)

    @property
    def is_configured(self) -> bool:
        return bool(self._vault_path) and self._vault_path.exists()

    def publish_summary(
        self,
        title: str,
        summary_markdown: str,
        tags: list[str] | None = None,
        recording_name: str | None = None,
        folder: str = "/",
        duration_seconds: int | None = None,
        cost_data: list[dict] | None = None,
    ) -> dict:
        if not self.is_configured:
            return {"ok": False, "error": f"Obsidian vault path does not exist: {self._vault_path}"}

        # Build output directory
        base_dir = self._vault_path / "AgenDino"
        if folder and folder != "/":
            folder_clean = folder.strip("/")
            base_dir = base_dir / folder_clean

        base_dir.mkdir(parents=True, exist_ok=True)

        # Build filename
        filename = self._sanitize_filename(title or recording_name or "untitled") + ".md"
        file_path = base_dir / filename

        # Build frontmatter
        frontmatter = self._build_frontmatter(
            title=title,
            tags=tags,
            recording_name=recording_name,
            folder=folder,
            duration_seconds=duration_seconds,
            cost_data=cost_data,
        )

        # Write file
        content = f"---\n{frontmatter}---\n\n{summary_markdown}"
        file_path.write_text(content, encoding="utf-8")

        logger.info("Exported summary to Obsidian: %s", file_path)
        return {"ok": True, "url": str(file_path)}

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Remove/replace characters that are problematic in filenames
        sanitized = re.sub(r'[<>:"/\\|?*]', "", name)
        sanitized = sanitized.strip(". ")
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip(". ")
        return sanitized or "untitled"

    @staticmethod
    def _build_frontmatter(
        title: str,
        tags: list[str] | None,
        recording_name: str | None,
        folder: str,
        duration_seconds: int | None,
        cost_data: list[dict] | None,
    ) -> str:
        lines = []
        lines.append(f"title: {title or 'Untitled'}")

        if tags:
            lines.append("tags:")
            for tag in tags:
                clean = tag.strip()
                if clean:
                    lines.append(f"  - {clean}")

        lines.append(f"source: agendino")

        if recording_name:
            lines.append(f"recording: {recording_name}")

        if folder and folder != "/":
            lines.append(f"folder: {folder}")

        if duration_seconds is not None:
            lines.append(f"duration_seconds: {duration_seconds}")

        # Cost breakdown from cost_data
        if cost_data:
            total_cost = sum(c.get("cost_usd", 0) for c in cost_data)
            for c in cost_data:
                op = c.get("operation", "unknown")
                lines.append(f"{op}:")
                lines.append(f"  engine: {c.get('engine', 'unknown')}")
                if c.get("model"):
                    lines.append(f"  model: {c['model']}")
                lines.append(f"  cost_usd: {c.get('cost_usd', 0)}")
                if c.get("input_units"):
                    lines.append(f"  input_units: {c['input_units']}")
                if c.get("output_units"):
                    lines.append(f"  output_units: {c['output_units']}")
            lines.append(f"total_cost_usd: {round(total_cost, 6)}")

        return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Commit**

```bash
git add src/services/ObsidianExportService.py
git commit -m "feat: add ObsidianExportService for local vault markdown export"
```

---

## Task 5: Wire Deepgram + Obsidian + Cost Tracking into DI + Controller

This is the core wiring task. It replaces the old Gemini transcription and Notion service with Deepgram and Obsidian, and adds cost tracking to transcription/summarization flows.

**Files:**
- Modify: `src/models/dto/TranscribeRequestDTO.py`
- Modify: `src/app/depends.py`
- Modify: `src/controllers/DashboardController.py`
- Delete: `src/services/TranscriptionService.py`
- Delete: `src/services/NotionService.py`

- [ ] **Step 1: Update TranscribeRequestDTO to accept "deepgram"**

Replace the contents of `src/models/dto/TranscribeRequestDTO.py`:

```python
from pydantic import BaseModel


class TranscribeRequestDTO(BaseModel):
    engine: str = "deepgram"  # "deepgram" or "whisper"
```

- [ ] **Step 2: Update depends.py — replace imports and add new factories**

Replace `src/app/depends.py` entirely. Key changes:
- Import `DeepgramTranscriptionService` instead of `TranscriptionService`
- Import `ObsidianExportService` instead of `NotionService`
- Import `CostTrackingRepository`
- Add `get_deepgram_transcription_service()`, `get_obsidian_export_service()`, `get_cost_tracking_repository()`
- Update `_build_publish_services()` to use Obsidian instead of Notion
- Update `get_dashboard_controller()` to inject new dependencies

```python
import os

from dotenv import load_dotenv

from controllers.CalendarController import CalendarController
from controllers.DashboardController import DashboardController
from controllers.ProactorController import ProactorController
from controllers.RAGController import RAGController
from repositories.CostTrackingRepository import CostTrackingRepository
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.SystemPromptsRepository import SystemPromptsRepository
from repositories.VectorStoreRepository import VectorStoreRepository
from services.DeepgramTranscriptionService import DeepgramTranscriptionService
from services.ObsidianExportService import ObsidianExportService
from services.RAGService import RAGService
from services.SummarizationService import SummarizationService
from services.TaskGenerationService import TaskGenerationService
from services.WhisperTranscriptionService import WhisperTranscriptionService
from services.DailyRecapService import DailyRecapService
from services.AuthService import AuthService
from services.ICalSyncService import ICalSyncService
from services.ProactorService import ProactorService

load_dotenv()

config = {}


def is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")


def get_config():
    if config.get("init", False):
        return config
    items = os.environ.items()
    for item in items:
        config[item[0]] = item[1]
    config["init"] = True
    return config


def get_root_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")


def get_template_path() -> str:
    return os.path.join(get_root_path(), "src/templates")


def get_sqlite_db_repository() -> SqliteDBRepository:
    _config = get_config()
    return SqliteDBRepository(
        db_name=_config["DATABASE_NAME"],
        db_path=os.path.join(get_root_path(), "settings"),
        init_sql_script=os.path.join(get_root_path(), "settings/db_init.sql"),
    )


def get_local_recordings_repository() -> LocalRecordingsRepository:
    return LocalRecordingsRepository(local_recordings_path=os.path.join(get_root_path(), "local_recordings"))


def get_deepgram_transcription_service() -> DeepgramTranscriptionService:
    _config = get_config()
    return DeepgramTranscriptionService(api_key=_config.get("DEEPGRAM_API_KEY", ""))


def get_whisper_transcription_service() -> WhisperTranscriptionService:
    _config = get_config()
    return WhisperTranscriptionService(
        model_size=_config["WHISPER_MODEL_SIZE"],
        device=_config["WHISPER_DEVICE"],
        compute_type=_config["WHISPER_COMPUTE_TYPE"],
    )


def get_summarization_service() -> SummarizationService:
    _config = get_config()
    return SummarizationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_task_generation_service() -> TaskGenerationService:
    _config = get_config()
    return TaskGenerationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_system_prompts_repository() -> SystemPromptsRepository:
    return SystemPromptsRepository(prompts_path=os.path.join(get_root_path(), "system_prompts"))


def get_obsidian_export_service() -> ObsidianExportService:
    _config = get_config()
    vault_path = _config.get("OBSIDIAN_VAULT_PATH", "")
    return ObsidianExportService(vault_path=vault_path)


def get_cost_tracking_repository() -> CostTrackingRepository:
    _config = get_config()
    db_path = os.path.join(get_root_path(), "settings", _config["DATABASE_NAME"])
    return CostTrackingRepository(db_path=db_path)


def _build_publish_services() -> dict:
    """Build a dict of configured publish services (only includes services with valid config)."""
    services = {}
    obsidian = get_obsidian_export_service()
    if obsidian.is_configured:
        services["obsidian"] = obsidian
    return services


def get_daily_recap_service() -> DailyRecapService:
    _config = get_config()
    return DailyRecapService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_dashboard_controller() -> DashboardController:
    return DashboardController(
        sqlite_db_repository=get_sqlite_db_repository(),
        local_recordings_repository=get_local_recordings_repository(),
        deepgram_transcription_service=get_deepgram_transcription_service(),
        summarization_service=get_summarization_service(),
        task_generation_service=get_task_generation_service(),
        system_prompts_repository=get_system_prompts_repository(),
        template_path=get_template_path(),
        publish_services=_build_publish_services(),
        whisper_transcription_service=get_whisper_transcription_service(),
        cost_tracking_repository=get_cost_tracking_repository(),
        auth_enabled=is_auth_enabled(),
    )


def get_calendar_controller() -> CalendarController:
    return CalendarController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        daily_recap_service=get_daily_recap_service(),
        ical_sync_service=ICalSyncService(),
        auth_enabled=is_auth_enabled(),
    )


def get_proactor_controller() -> ProactorController:
    return ProactorController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        proactor_service=ProactorService(),
        auth_enabled=is_auth_enabled(),
    )


def get_vector_store_repository() -> VectorStoreRepository:
    _config = get_config()
    return VectorStoreRepository(
        persist_path=os.path.join(get_root_path(), "settings/vector_store"),
        api_key=_config["GEMINI_API_KEY"],
        model=_config["GEMINI_EMBEDDING_MODEL"],
    )


def get_rag_service() -> RAGService:
    _config = get_config()
    return RAGService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_rag_controller() -> RAGController:
    return RAGController(
        sqlite_db_repository=get_sqlite_db_repository(),
        vector_store_repository=get_vector_store_repository(),
        rag_service=get_rag_service(),
        template_path=get_template_path(),
        auth_enabled=is_auth_enabled(),
    )


def get_auth_service() -> AuthService:
    return AuthService(settings_path=os.path.join(get_root_path(), "settings"))
```

- [ ] **Step 3: Update DashboardController constructor and imports**

In `src/controllers/DashboardController.py`, make these changes:

**Replace the imports** (lines 1-17):

```python
from __future__ import annotations

import os
from datetime import datetime

from fastapi import Request
from fastapi.templating import Jinja2Templates

from models.DBRecording import DBRecording
from models.DBTask import DBTask
from models.dto.CostMetadata import CostMetadata
from repositories.CostTrackingRepository import CostTrackingRepository
from repositories.LocalRecordingsRepository import LocalRecordingsRepository, ALLOWED_AUDIO_EXTENSIONS
from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.SystemPromptsRepository import SystemPromptsRepository
from services.DeepgramTranscriptionService import DeepgramTranscriptionService
from services.SummarizationService import SummarizationService
from services.TaskGenerationService import TaskGenerationService
from services.WhisperTranscriptionService import WhisperTranscriptionService
```

**Replace the constructor** (lines 32-55):

```python
class DashboardController:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        local_recordings_repository: LocalRecordingsRepository,
        deepgram_transcription_service: DeepgramTranscriptionService,
        summarization_service: SummarizationService,
        task_generation_service: TaskGenerationService,
        system_prompts_repository: SystemPromptsRepository,
        template_path: str,
        publish_services: dict[str, object] | None = None,
        whisper_transcription_service: WhisperTranscriptionService | None = None,
        cost_tracking_repository: CostTrackingRepository | None = None,
        auth_enabled: bool = False,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._local_recordings_repository = local_recordings_repository
        self._deepgram_transcription_service = deepgram_transcription_service
        self._summarization_service = summarization_service
        self._task_generation_service = task_generation_service
        self._system_prompts_repository = system_prompts_repository
        self._templates = Jinja2Templates(directory=template_path)
        self._publish_services: dict[str, object] = publish_services or {}
        self._whisper_transcription_service = whisper_transcription_service
        self._cost_tracking_repository = cost_tracking_repository
        self._auth_enabled = auth_enabled
```

- [ ] **Step 4: Update transcribe_recording method**

Replace the `transcribe_recording` method (lines 322-350):

```python
    def transcribe_recording(self, name: str, engine: str = "deepgram") -> dict:
        bare_name = self._bare_name(name)
        local_filename, file_ext = self._resolve_local_filename(bare_name)

        if not self._local_recordings_repository.exists(local_filename):
            return {"ok": False, "error": f"Local file '{local_filename}' not found"}

        db_rec = self._sqlite_db_repository.get_recording_by_name(bare_name)
        if db_rec and db_rec.transcript:
            return {"ok": True, "transcript": db_rec.transcript, "cached": True}

        audio_path = self._local_recordings_repository.get_path(local_filename)
        mime_type = MIME_TYPES.get(file_ext, "audio/mpeg")

        try:
            if engine == "whisper":
                if not self._whisper_transcription_service:
                    return {"ok": False, "error": "Whisper transcription service is not available"}
                transcript = self._whisper_transcription_service.transcribe(audio_path, mime_type=mime_type)
                cost = CostMetadata(
                    operation="transcription", engine="whisper", model="local",
                    input_units=0, output_units=0, cost_usd=0.0,
                )
            else:
                transcript, cost = self._deepgram_transcription_service.transcribe(audio_path, mime_type=mime_type)
        except Exception as e:
            return {"ok": False, "error": f"Transcription failed: {str(e)}"}

        self._sqlite_db_repository.save_transcript(bare_name, transcript)

        # Track cost
        recording_id = db_rec.id if db_rec else None
        if self._cost_tracking_repository and recording_id:
            self._cost_tracking_repository.save(recording_id, cost)

        return {"ok": True, "transcript": transcript, "cached": False}
```

- [ ] **Step 5: Update publish destination metadata**

Replace the `_DESTINATION_META` dict (line 505-507):

```python
    _DESTINATION_META: dict[str, dict] = {
        "obsidian": {"label": "Obsidian", "icon": "bi-journal-text"},
    }
```

- [ ] **Step 6: Update publish_summary method to pass folder/duration/cost data**

Replace the `publish_summary` method (lines 533-562):

```python
    def publish_summary(self, summary_id: int, destination: str) -> dict:
        svc = self._publish_services.get(destination)
        if not svc:
            return {"ok": False, "error": f"Unknown publish destination: {destination}"}

        summary = self._sqlite_db_repository.get_summary_by_id(summary_id)
        if not summary:
            return {"ok": False, "error": "Summary not found"}

        title = summary.title or summary.recording_name
        tags = summary.tags.split(",") if summary.tags else []

        publish_title = title
        recording_dt = self._parse_recording_datetime(summary.recording_name)
        if recording_dt:
            date_only = recording_dt.split(" ")[0]
            publish_title = f"{date_only} {title}"

        # Get recording metadata for Obsidian export
        db_rec = self._sqlite_db_repository.get_recording_by_name(summary.recording_name)
        folder = db_rec.folder if db_rec else "/"
        duration = db_rec.duration if db_rec else None

        # Get cost data for frontmatter
        cost_data = None
        if self._cost_tracking_repository and db_rec:
            cost_data = self._cost_tracking_repository.get_by_recording(db_rec.id)

        try:
            result = svc.publish_summary(
                title=publish_title,
                summary_markdown=summary.summary,
                tags=tags,
                recording_name=summary.recording_name,
                folder=folder,
                duration_seconds=duration,
                cost_data=cost_data,
            )
            return result
        except Exception as e:
            return {"ok": False, "error": f"Publish failed: {str(e)}"}
```

- [ ] **Step 7: Delete old services**

```bash
git rm src/services/TranscriptionService.py
git rm src/services/NotionService.py
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: replace Gemini transcription with Deepgram, Notion with Obsidian, add cost tracking"
```

---

## Task 6: Update Frontend — Engine Dropdown + Publish UI

**Files:**
- Modify: `src/static/dashboard.js`
- Modify: `src/templates/dashboard/home.html` (share modal)

- [ ] **Step 1: Update transcription engine dropdown in dashboard.js**

In `src/static/dashboard.js`, find the engine dropdown HTML (around line 71-77) and replace:

Old (find this block):
```javascript
            btns.push(`<div class="btn-group btn-group-sm transcribe-split" style="position:relative">
                <button class="btn btn-outline-primary btn-transcribe" data-name="${rec.name}" data-engine="gemini" title="Transcribe with Gemini"><i class="bi bi-mic"></i></button>
                <button type="button" class="btn btn-outline-primary btn-transcribe-toggle" data-name="${rec.name}" title="Choose engine" style="padding-left:3px;padding-right:3px;border-left:0"><i class="bi bi-caret-down-fill" style="font-size:.55em"></i></button>
                <div class="transcribe-engine-menu d-none" style="position:absolute;top:100%;right:0;z-index:1050;min-width:160px;background:var(--bs-body-bg);border:1px solid var(--bs-border-color);border-radius:.375rem;box-shadow:0 .5rem 1rem rgba(0,0,0,.15);margin-top:2px">
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="gemini" style="font-size:.85rem"><i class="bi bi-cloud"></i> Gemini</a>
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="whisper" style="font-size:.85rem;border-top:1px solid var(--bs-border-color)"><i class="bi bi-pc-display"></i> Whisper (local)</a>
                </div>
            </div>`);
```

New:
```javascript
            btns.push(`<div class="btn-group btn-group-sm transcribe-split" style="position:relative">
                <button class="btn btn-outline-primary btn-transcribe" data-name="${rec.name}" data-engine="deepgram" title="Transcribe with Deepgram"><i class="bi bi-mic"></i></button>
                <button type="button" class="btn btn-outline-primary btn-transcribe-toggle" data-name="${rec.name}" title="Choose engine" style="padding-left:3px;padding-right:3px;border-left:0"><i class="bi bi-caret-down-fill" style="font-size:.55em"></i></button>
                <div class="transcribe-engine-menu d-none" style="position:absolute;top:100%;right:0;z-index:1050;min-width:160px;background:var(--bs-body-bg);border:1px solid var(--bs-border-color);border-radius:.375rem;box-shadow:0 .5rem 1rem rgba(0,0,0,.15);margin-top:2px">
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="deepgram" style="font-size:.85rem"><i class="bi bi-cloud"></i> Deepgram Nova</a>
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="whisper" style="font-size:.85rem;border-top:1px solid var(--bs-border-color)"><i class="bi bi-pc-display"></i> Whisper (local)</a>
                </div>
            </div>`);
```

- [ ] **Step 2: Update engine label in startTranscription function**

In `src/static/dashboard.js`, find line ~1251:

Old:
```javascript
    async function startTranscription(name, engine, triggerBtn) {
        const engineLabel = engine === "whisper" ? "Whisper (local)" : "Gemini AI";
```

New:
```javascript
    async function startTranscription(name, engine, triggerBtn) {
        const engineLabel = engine === "whisper" ? "Whisper (local)" : "Deepgram Nova";
```

- [ ] **Step 3: Update summarization status message**

In `src/static/dashboard.js`, find line ~1733:

Old:
```javascript
        summaryLoading.querySelector("p").textContent = "Generating summary with Gemini AI… this may take a moment.";
```

New:
```javascript
        summaryLoading.querySelector("p").textContent = "Generating summary… this may take a moment.";
```

- [ ] **Step 4: Update share modal — "Open in Notion" → "Open in Obsidian"**

In `src/templates/dashboard/home.html`, find line 285:

Old:
```html
                            <i class="bi bi-box-arrow-up-right me-1"></i>Open in Notion
```

New:
```html
                            <i class="bi bi-box-arrow-up-right me-1"></i>Open
```

- [ ] **Step 5: Update share error message in dashboard.js**

In `src/static/dashboard.js`, find the share destinations error message (~line 1820):

Old:
```javascript
                shareError.textContent = "No publish destinations configured. Set NOTION_API_KEY and NOTION_DATABASE_ID in your .env file.";
```

New:
```javascript
                shareError.textContent = "No export destinations configured. Set OBSIDIAN_VAULT_PATH in your .env file.";
```

- [ ] **Step 6: Update notion_url references in dashboard.js**

In `src/static/dashboard.js`, find the title rendering that links to Notion (around line 118-119):

Old:
```javascript
    if (rec.db_title && rec.notion_url) {
        titleStr = `<a href="${rec.notion_url}" target="_blank" rel="noopener" class="text-decoration-none" title="Open in Notion">${rec.db_title} <i class="bi bi-box-arrow-up-right small text-muted"></i></a>`;
```

New:
```javascript
    if (rec.db_title) {
        titleStr = rec.db_title;
```

- [ ] **Step 7: Remove the notion_url rendering from the summary version cards**

In `src/static/dashboard.js`, find the notionLink variable (around line 1532-1533):

Old:
```javascript
            const notionLink = s.notion_url
                ? `<a href="${escapeHtml(s.notion_url)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-success"><i class="bi bi-box-arrow-up-right me-1"></i>Open</a>`
                : "";
```

New:
```javascript
            const notionLink = "";
```

- [ ] **Step 8: Commit**

```bash
git add src/static/dashboard.js src/templates/dashboard/home.html
git commit -m "feat: update UI for Deepgram transcription engine and Obsidian export"
```

---

## Task 7: Markdown System Prompts

**Files:**
- Modify: `src/repositories/SystemPromptsRepository.py`

- [ ] **Step 1: Update SystemPromptsRepository to support .md files**

In `src/repositories/SystemPromptsRepository.py`, make two changes:

**Change 1** — In `_collect_prompts`, replace line 26:

Old:
```python
            if prompt_file.is_file() and prompt_file.suffix == ".txt":
```

New:
```python
            if prompt_file.is_file() and prompt_file.suffix in (".txt", ".md"):
```

**Change 2** — In `get_prompt_content`, replace lines 39-43:

Old:
```python
    def get_prompt_content(self, prompt_id: str) -> str | None:
        prompt_path = self._prompts_dir / f"{prompt_id}.txt"
        if not prompt_path.exists():
            return None
        return prompt_path.read_text(encoding="utf-8")
```

New:
```python
    def get_prompt_content(self, prompt_id: str) -> str | None:
        # Try .txt first, then .md
        for ext in (".txt", ".md"):
            prompt_path = self._prompts_dir / f"{prompt_id}{ext}"
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        return None
```

- [ ] **Step 2: Commit**

```bash
git add src/repositories/SystemPromptsRepository.py
git commit -m "feat: support .md files alongside .txt for system prompts"
```

---

## Task 8: Stats Dashboard — API + Web + Template

**Files:**
- Create: `src/app/api/endpoints/stats.py`
- Create: `src/app/web/stats.py`
- Create: `src/templates/stats.html`
- Modify: `src/app/api/api.py`
- Modify: `src/app/router.py`
- Modify: `src/templates/base.html` (add sidebar link)

- [ ] **Step 1: Create stats API endpoint**

Create `src/app/api/endpoints/stats.py`:

```python
from fastapi import APIRouter, Depends

from app import depends
from repositories.CostTrackingRepository import CostTrackingRepository

router = APIRouter()


@router.get("/totals")
async def get_totals(
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, **cost_repo.get_totals()}


@router.get("/by-engine")
async def get_by_engine(
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, "data": cost_repo.get_by_engine()}


@router.get("/daily")
async def get_daily_totals(
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, "data": cost_repo.get_daily_totals()}


@router.get("/per-recording")
async def get_per_recording(
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, "data": cost_repo.get_per_recording_costs()}


@router.get("/usage")
async def get_usage_counts(
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, **cost_repo.get_usage_counts()}


@router.get("/range")
async def get_by_range(
    start: str,
    end: str,
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    return {"ok": True, "data": cost_repo.get_by_date_range(start, end)}
```

- [ ] **Step 2: Create stats web handler**

Create `src/app/web/stats.py`:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import depends

router = APIRouter()


@router.get("/stats", response_class=HTMLResponse)
def stats_home(request: Request):
    template_path = depends.get_template_path()
    templates = Jinja2Templates(directory=template_path)
    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={"active_page": "stats", "auth_enabled": depends.is_auth_enabled()},
    )
```

- [ ] **Step 3: Create stats template**

Create `src/templates/stats.html`:

```html
{% extends "base.html" %}

{% block title %}Stats{% endblock %}
{% block page_header %}API Usage & Costs{% endblock %}

{% block extra_head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
{% endblock %}

{% block content %}
<!-- Summary Cards -->
<div class="row mb-4" id="stats-cards">
    <div class="col-lg-3 col-6">
        <div class="small-box text-bg-primary">
            <div class="inner">
                <h3 id="stat-total-cost">$-</h3>
                <p>Total Spend</p>
            </div>
            <div class="icon"><i class="bi bi-currency-dollar"></i></div>
        </div>
    </div>
    <div class="col-lg-3 col-6">
        <div class="small-box text-bg-success">
            <div class="inner">
                <h3 id="stat-transcriptions">-</h3>
                <p>Transcriptions</p>
            </div>
            <div class="icon"><i class="bi bi-mic"></i></div>
        </div>
    </div>
    <div class="col-lg-3 col-6">
        <div class="small-box text-bg-warning">
            <div class="inner">
                <h3 id="stat-summarizations">-</h3>
                <p>Summarizations</p>
            </div>
            <div class="icon"><i class="bi bi-stars"></i></div>
        </div>
    </div>
    <div class="col-lg-3 col-6">
        <div class="small-box text-bg-info">
            <div class="inner">
                <h3 id="stat-operations">-</h3>
                <p>Total Operations</p>
            </div>
            <div class="icon"><i class="bi bi-activity"></i></div>
        </div>
    </div>
</div>

<div class="row mb-4">
    <!-- Spend Over Time -->
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header"><h5 class="card-title mb-0">Daily Spend</h5></div>
            <div class="card-body">
                <canvas id="chart-daily-spend" height="300"></canvas>
            </div>
        </div>
    </div>
    <!-- By Engine -->
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header"><h5 class="card-title mb-0">Spend by Engine</h5></div>
            <div class="card-body">
                <canvas id="chart-by-engine" height="300"></canvas>
            </div>
        </div>
    </div>
</div>

<!-- Per-Recording Costs Table -->
<div class="card mb-4">
    <div class="card-header"><h5 class="card-title mb-0">Cost per Recording</h5></div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-striped table-hover mb-0">
                <thead>
                    <tr>
                        <th>Recording</th>
                        <th>Folder</th>
                        <th class="text-end">Transcription</th>
                        <th class="text-end">Summarization</th>
                        <th class="text-end">Total</th>
                        <th class="text-center">Est.</th>
                    </tr>
                </thead>
                <tbody id="cost-table-body">
                    <tr><td colspan="6" class="text-center text-muted py-4">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function() {
    const API = "/api/stats";
    const fmt = (v) => `$${Number(v).toFixed(4)}`;

    async function loadStats() {
        const [totals, usage, daily, byEngine, perRec] = await Promise.all([
            fetch(`${API}/totals`).then(r => r.json()),
            fetch(`${API}/usage`).then(r => r.json()),
            fetch(`${API}/daily`).then(r => r.json()),
            fetch(`${API}/by-engine`).then(r => r.json()),
            fetch(`${API}/per-recording`).then(r => r.json()),
        ]);

        // Summary cards
        document.getElementById("stat-total-cost").textContent = fmt(totals.total_cost);
        document.getElementById("stat-transcriptions").textContent = usage.transcriptions || 0;
        document.getElementById("stat-summarizations").textContent = usage.summarizations || 0;
        document.getElementById("stat-operations").textContent = totals.total_operations || 0;

        // Daily spend chart
        if (daily.data && daily.data.length > 0) {
            new Chart(document.getElementById("chart-daily-spend"), {
                type: "bar",
                data: {
                    labels: daily.data.map(d => d.date),
                    datasets: [{
                        label: "Spend ($)",
                        data: daily.data.map(d => d.total_cost),
                        backgroundColor: "rgba(13, 110, 253, 0.7)",
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true } },
                    plugins: { legend: { display: false } },
                }
            });
        }

        // By engine chart
        if (byEngine.data && byEngine.data.length > 0) {
            const engineMap = {};
            byEngine.data.forEach(d => {
                engineMap[d.engine] = (engineMap[d.engine] || 0) + d.total_cost;
            });
            const engines = Object.keys(engineMap);
            const colors = ["rgba(13,110,253,0.7)", "rgba(25,135,84,0.7)", "rgba(255,193,7,0.7)", "rgba(220,53,69,0.7)"];
            new Chart(document.getElementById("chart-by-engine"), {
                type: "doughnut",
                data: {
                    labels: engines.map(e => e.charAt(0).toUpperCase() + e.slice(1)),
                    datasets: [{
                        data: engines.map(e => engineMap[e]),
                        backgroundColor: colors.slice(0, engines.length),
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                }
            });
        }

        // Per-recording table
        const tbody = document.getElementById("cost-table-body");
        if (perRec.data && perRec.data.length > 0) {
            tbody.innerHTML = perRec.data.map(r => `
                <tr>
                    <td>${r.name}</td>
                    <td><span class="badge bg-secondary">${r.folder}</span></td>
                    <td class="text-end">${fmt(r.transcription_cost)}</td>
                    <td class="text-end">${fmt(r.summarization_cost)}</td>
                    <td class="text-end fw-bold">${fmt(r.total_cost)}</td>
                    <td class="text-center">${r.has_estimates ? '<i class="bi bi-clock text-warning" title="Includes estimates"></i>' : ''}</td>
                </tr>
            `).join("");
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No cost data yet. Transcribe or summarize a recording to start tracking.</td></tr>';
        }
    }

    loadStats();
})();
</script>
{% endblock %}
```

- [ ] **Step 4: Register stats API router**

In `src/app/api/api.py`, add:

```python
from .endpoints import stats
```

And add this line after the existing `router.include_router` calls:

```python
router.include_router(stats.router, prefix="/stats")
```

- [ ] **Step 5: Register stats web router**

In `src/app/router.py`, add:

```python
from app.web.stats import router as stats_router
```

And add this line after the existing `router.include_router` calls:

```python
router.include_router(stats_router, prefix="")
```

- [ ] **Step 6: Add stats link to sidebar**

In `src/templates/base.html`, add a new sidebar item after the Knowledge Base item (after line 65):

```html
                        <li class="nav-item">
                            <a href="/stats" class="nav-link {{ 'active' if active_page == 'stats' }}">
                                <i class="nav-icon bi bi-graph-up"></i>
                                <p>Stats</p>
                            </a>
                        </li>
```

- [ ] **Step 7: Commit**

```bash
git add src/app/api/endpoints/stats.py src/app/web/stats.py src/templates/stats.html src/app/api/api.py src/app/router.py src/templates/base.html
git commit -m "feat: add stats dashboard with cost tracking charts and tables"
```

---

## Task 9: Model Comparison Lab — Service + API + Template

**Files:**
- Create: `src/services/ModelRegistry.py`
- Create: `src/app/api/endpoints/compare.py`
- Create: `src/app/web/compare.py`
- Create: `src/templates/compare.html`
- Modify: `src/app/api/api.py`
- Modify: `src/app/router.py`
- Modify: `src/templates/base.html` (add sidebar link)
- Modify: `src/app/depends.py`

- [ ] **Step 1: Create ModelRegistry**

Create `src/services/ModelRegistry.py`:

```python
from dataclasses import dataclass


@dataclass
class EngineInfo:
    id: str
    name: str
    type: str        # 'transcription', 'summarization', 'both'
    available: bool


class ModelRegistry:
    def __init__(self, deepgram_available: bool, whisper_available: bool, gemini_available: bool):
        self._engines = [
            EngineInfo(id="deepgram", name="Deepgram Nova", type="transcription", available=deepgram_available),
            EngineInfo(id="whisper", name="Whisper (local)", type="transcription", available=whisper_available),
            EngineInfo(id="gemini", name="Gemini", type="summarization", available=gemini_available),
        ]

    def get_transcription_engines(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available and e.type in ("transcription", "both")]

    def get_summarization_engines(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available and e.type in ("summarization", "both")]

    def get_all_available(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available]

    def to_dict_list(self, engines: list[EngineInfo] | None = None) -> list[dict]:
        targets = engines or self.get_all_available()
        return [{"id": e.id, "name": e.name, "type": e.type} for e in targets]
```

- [ ] **Step 2: Add ModelRegistry + ComparisonRepository methods to depends.py**

In `src/app/depends.py`, add the import:

```python
from services.ModelRegistry import ModelRegistry
```

Add these factory functions:

```python
def get_model_registry() -> ModelRegistry:
    _config = get_config()
    return ModelRegistry(
        deepgram_available=bool(_config.get("DEEPGRAM_API_KEY")),
        whisper_available=True,  # Always available (local)
        gemini_available=bool(_config.get("GEMINI_API_KEY")),
    )
```

- [ ] **Step 3: Add comparison DB methods to SqliteDBRepository**

In `src/repositories/SqliteDBRepository.py`, add these methods at the end of the class:

```python
    # ─── Comparison ──────────────────────────────────────────────

    def create_comparison_run(self, recording_id: int, run_type: str) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO comparison_run (recording_id, run_type) VALUES (?, ?)",
                (recording_id, run_type),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_comparison_result(self, run_id: int, engine: str, model: str | None,
                              system_prompt_id: str | None, output_text: str,
                              cost_usd: float, processing_time_ms: int | None) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO comparison_result
                   (run_id, engine, model, system_prompt_id, output_text, cost_usd, processing_time_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, engine, model, system_prompt_id, output_text, cost_usd, processing_time_ms),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_comparison_feedback(self, run_id: int, preferred_result_id: int | None,
                                 segment_index: int | None, notes: str | None) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO comparison_feedback
                   (run_id, segment_index, preferred_result_id, notes) VALUES (?, ?, ?, ?)""",
                (run_id, segment_index, preferred_result_id, notes),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_comparison_runs(self, recording_id: int | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if recording_id:
                rows = conn.execute(
                    """SELECT cr.*, r.name as recording_name
                       FROM comparison_run cr JOIN recording r ON cr.recording_id = r.id
                       WHERE cr.recording_id = ? ORDER BY cr.created_at DESC""",
                    (recording_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT cr.*, r.name as recording_name
                       FROM comparison_run cr JOIN recording r ON cr.recording_id = r.id
                       ORDER BY cr.created_at DESC LIMIT 50"""
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_comparison_results(self, run_id: int) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM comparison_result WHERE run_id = ? ORDER BY id", (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_comparison_feedback(self, run_id: int) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM comparison_feedback WHERE run_id = ? ORDER BY id", (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 4: Create compare API endpoint**

Create `src/app/api/endpoints/compare.py`:

```python
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import depends
from models.dto.CostMetadata import CostMetadata
from repositories.CostTrackingRepository import CostTrackingRepository
from repositories.SqliteDBRepository import SqliteDBRepository
from services.ModelRegistry import ModelRegistry

router = APIRouter()


class TranscriptionCompareRequest(BaseModel):
    recording_name: str
    engines: list[str]  # ["deepgram", "whisper"]


class SummarizationCompareRequest(BaseModel):
    recording_name: str
    prompt_ids: list[str]  # multiple prompts to compare


class FeedbackRequest(BaseModel):
    run_id: int
    preferred_result_id: int | None = None
    segment_index: int | None = None
    notes: str | None = None


@router.get("/engines")
async def list_engines(
    registry: ModelRegistry = Depends(depends.get_model_registry),
):
    return {
        "ok": True,
        "transcription": registry.to_dict_list(registry.get_transcription_engines()),
        "summarization": registry.to_dict_list(registry.get_summarization_engines()),
    }


@router.post("/transcription")
async def compare_transcription(
    body: TranscriptionCompareRequest,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    from repositories.LocalRecordingsRepository import LocalRecordingsRepository, ALLOWED_AUDIO_EXTENSIONS
    import os

    bare_name = body.recording_name
    db_rec = db.get_recording_by_name(bare_name)
    if not db_rec:
        return {"ok": False, "error": f"Recording '{bare_name}' not found"}

    # Resolve audio file
    local_repo = depends.get_local_recordings_repository()
    ext = db_rec.file_extension
    local_filename = f"{bare_name}.{ext}"
    if not local_repo.exists(local_filename):
        return {"ok": False, "error": f"Audio file '{local_filename}' not found"}

    audio_path = local_repo.get_path(local_filename)
    mime_type = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
                 "ogg": "audio/ogg", "hda": "audio/mpeg"}.get(ext, "audio/mpeg")

    run_id = db.create_comparison_run(db_rec.id, "transcription")
    results = []

    for engine_id in body.engines:
        start_ms = time.time()
        try:
            if engine_id == "deepgram":
                svc = depends.get_deepgram_transcription_service()
                transcript, cost = svc.transcribe(audio_path, mime_type=mime_type)
            elif engine_id == "whisper":
                svc = depends.get_whisper_transcription_service()
                transcript = svc.transcribe(audio_path, mime_type=mime_type)
                cost = CostMetadata("transcription", "whisper", "local", 0, 0, 0.0)
            else:
                continue

            elapsed_ms = int((time.time() - start_ms) * 1000)
            result_id = db.add_comparison_result(
                run_id, engine_id, cost.model, None, transcript, cost.cost_usd, elapsed_ms,
            )
            cost_repo.save(db_rec.id, CostMetadata(
                "comparison", cost.engine, cost.model, cost.input_units, cost.output_units, cost.cost_usd,
            ))
            results.append({
                "id": result_id, "engine": engine_id, "model": cost.model,
                "transcript": transcript, "cost_usd": cost.cost_usd,
                "processing_time_ms": elapsed_ms,
            })
        except Exception as e:
            elapsed_ms = int((time.time() - start_ms) * 1000)
            result_id = db.add_comparison_result(
                run_id, engine_id, None, None, f"Error: {e}", 0, elapsed_ms,
            )
            results.append({
                "id": result_id, "engine": engine_id, "error": str(e),
                "processing_time_ms": elapsed_ms,
            })

    return {"ok": True, "run_id": run_id, "results": results}


@router.post("/summarization")
async def compare_summarization(
    body: SummarizationCompareRequest,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
    cost_repo: CostTrackingRepository = Depends(depends.get_cost_tracking_repository),
):
    bare_name = body.recording_name
    db_rec = db.get_recording_by_name(bare_name)
    if not db_rec:
        return {"ok": False, "error": f"Recording '{bare_name}' not found"}

    transcript = db.get_transcript(bare_name)
    if not transcript:
        return {"ok": False, "error": "No transcript found — transcribe first"}

    prompts_repo = depends.get_system_prompts_repository()
    summarization_svc = depends.get_summarization_service()

    run_id = db.create_comparison_run(db_rec.id, "summarization")
    results = []

    for prompt_id in body.prompt_ids:
        prompt_content = prompts_repo.get_prompt_content(prompt_id)
        if not prompt_content:
            results.append({"prompt_id": prompt_id, "error": f"Prompt '{prompt_id}' not found"})
            continue

        start_ms = time.time()
        try:
            result = summarization_svc.summarize(transcript, prompt_content)
            elapsed_ms = int((time.time() - start_ms) * 1000)
            output_text = result.get("summary", "")
            result_id = db.add_comparison_result(
                run_id, "gemini", summarization_svc._model, prompt_id, output_text, 0, elapsed_ms,
            )
            results.append({
                "id": result_id, "prompt_id": prompt_id, "engine": "gemini",
                "title": result.get("title", ""), "summary": output_text,
                "processing_time_ms": elapsed_ms,
            })
        except Exception as e:
            elapsed_ms = int((time.time() - start_ms) * 1000)
            results.append({"prompt_id": prompt_id, "error": str(e), "processing_time_ms": elapsed_ms})

    return {"ok": True, "run_id": run_id, "results": results}


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
):
    feedback_id = db.add_comparison_feedback(
        body.run_id, body.preferred_result_id, body.segment_index, body.notes,
    )
    return {"ok": True, "feedback_id": feedback_id}


@router.get("/history")
async def get_history(
    recording_name: str | None = None,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
):
    if recording_name:
        db_rec = db.get_recording_by_name(recording_name)
        if not db_rec:
            return {"ok": False, "error": "Recording not found"}
        runs = db.get_comparison_runs(db_rec.id)
    else:
        runs = db.get_comparison_runs()
    return {"ok": True, "runs": runs}


@router.get("/run/{run_id}")
async def get_run_detail(
    run_id: int,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
):
    results = db.get_comparison_results(run_id)
    feedback = db.get_comparison_feedback(run_id)
    return {"ok": True, "results": results, "feedback": feedback}
```

- [ ] **Step 5: Create compare web handler**

Create `src/app/web/compare.py`:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import depends

router = APIRouter()


@router.get("/compare", response_class=HTMLResponse)
def compare_home(request: Request):
    template_path = depends.get_template_path()
    templates = Jinja2Templates(directory=template_path)
    return templates.TemplateResponse(
        request=request,
        name="compare.html",
        context={"active_page": "compare", "auth_enabled": depends.is_auth_enabled()},
    )
```

- [ ] **Step 6: Create compare template**

Create `src/templates/compare.html`:

```html
{% extends "base.html" %}

{% block title %}Compare{% endblock %}
{% block page_header %}Model Comparison Lab{% endblock %}

{% block content %}
<!-- Setup -->
<div class="card mb-4">
    <div class="card-header"><h5 class="card-title mb-0">New Comparison</h5></div>
    <div class="card-body">
        <div class="row g-3">
            <div class="col-md-4">
                <label class="form-label fw-bold">Recording</label>
                <select class="form-select" id="compare-recording">
                    <option value="">Loading...</option>
                </select>
            </div>
            <div class="col-md-4">
                <label class="form-label fw-bold">Type</label>
                <select class="form-select" id="compare-type">
                    <option value="transcription">Transcription</option>
                    <option value="summarization">Summarization</option>
                </select>
            </div>
            <div class="col-md-4">
                <label class="form-label fw-bold d-block">&nbsp;</label>
                <button class="btn btn-primary" id="btn-run-compare" disabled>
                    <i class="bi bi-play-fill me-1"></i>Run Comparison
                </button>
            </div>
        </div>
        <!-- Engine / Prompt selection -->
        <div class="mt-3" id="engine-selection">
            <label class="form-label fw-bold">Engines</label>
            <div id="engine-checkboxes" class="d-flex gap-3 flex-wrap"></div>
        </div>
        <div class="mt-3 d-none" id="prompt-selection">
            <label class="form-label fw-bold">System Prompts to Compare</label>
            <div id="prompt-checkboxes" class="d-flex gap-3 flex-wrap"></div>
        </div>
    </div>
</div>

<!-- Results -->
<div class="card mb-4 d-none" id="compare-results-card">
    <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="card-title mb-0">Results</h5>
        <span class="badge bg-secondary" id="compare-run-id"></span>
    </div>
    <div class="card-body" id="compare-results"></div>
</div>

<!-- History -->
<div class="card mb-4">
    <div class="card-header"><h5 class="card-title mb-0">Comparison History</h5></div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-striped table-hover mb-0">
                <thead><tr><th>Run</th><th>Recording</th><th>Type</th><th>Date</th></tr></thead>
                <tbody id="history-body">
                    <tr><td colspan="4" class="text-center text-muted py-4">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function() {
    const $ = (s) => document.querySelector(s);
    const recSelect = $("#compare-recording");
    const typeSelect = $("#compare-type");
    const runBtn = $("#btn-run-compare");
    const engineSection = $("#engine-selection");
    const promptSection = $("#prompt-selection");
    const engineBoxes = $("#engine-checkboxes");
    const promptBoxes = $("#prompt-checkboxes");
    const resultsCard = $("#compare-results-card");
    const resultsDiv = $("#compare-results");
    const runIdBadge = $("#compare-run-id");
    const historyBody = $("#history-body");

    // Load recordings
    fetch("/api/dashboard/recordings").then(r => r.json()).then(data => {
        recSelect.innerHTML = '<option value="">Select recording...</option>';
        (data.recordings || []).forEach(r => {
            const opt = document.createElement("option");
            opt.value = r.name;
            opt.textContent = r.db_title || r.name;
            recSelect.appendChild(opt);
        });
        recSelect.addEventListener("change", () => { runBtn.disabled = !recSelect.value; });
    });

    // Load engines
    fetch("/api/compare/engines").then(r => r.json()).then(data => {
        engineBoxes.innerHTML = data.transcription.map(e =>
            `<div class="form-check"><input class="form-check-input engine-cb" type="checkbox" value="${e.id}" id="eng-${e.id}" checked><label class="form-check-label" for="eng-${e.id}">${e.name}</label></div>`
        ).join("");
    });

    // Load prompts
    fetch("/api/dashboard/prompts").then(r => r.json()).then(data => {
        if (data.ok) {
            promptBoxes.innerHTML = data.prompts.map(p =>
                `<div class="form-check"><input class="form-check-input prompt-cb" type="checkbox" value="${p.id}" id="prompt-${p.id.replace(/\//g,'-')}" checked><label class="form-check-label" for="prompt-${p.id.replace(/\//g,'-')}">${p.label}</label></div>`
            ).join("");
        }
    });

    // Toggle engine vs prompt selection
    typeSelect.addEventListener("change", () => {
        if (typeSelect.value === "transcription") {
            engineSection.classList.remove("d-none");
            promptSection.classList.add("d-none");
        } else {
            engineSection.classList.add("d-none");
            promptSection.classList.remove("d-none");
        }
    });

    // Run comparison
    runBtn.addEventListener("click", async () => {
        const name = recSelect.value;
        if (!name) return;
        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running...';
        resultsCard.classList.remove("d-none");
        resultsDiv.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div><p class="mt-2 text-muted">Running comparison... this may take a while.</p></div>';

        const isTranscription = typeSelect.value === "transcription";
        let url, body;

        if (isTranscription) {
            const engines = [...document.querySelectorAll(".engine-cb:checked")].map(cb => cb.value);
            url = "/api/compare/transcription";
            body = { recording_name: name, engines };
        } else {
            const prompts = [...document.querySelectorAll(".prompt-cb:checked")].map(cb => cb.value);
            url = "/api/compare/summarization";
            body = { recording_name: name, prompt_ids: prompts };
        }

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (data.ok) {
                runIdBadge.textContent = `Run #${data.run_id}`;
                resultsDiv.innerHTML = data.results.map(r => {
                    const header = r.engine || r.prompt_id;
                    const content = r.error
                        ? `<div class="alert alert-danger">${r.error}</div>`
                        : `<pre class="bg-body-secondary p-3 rounded" style="max-height:400px;overflow:auto;white-space:pre-wrap">${escapeHtml(r.transcript || r.summary || "")}</pre>`;
                    const meta = [];
                    if (r.cost_usd !== undefined) meta.push(`$${Number(r.cost_usd).toFixed(4)}`);
                    if (r.processing_time_ms) meta.push(`${(r.processing_time_ms/1000).toFixed(1)}s`);
                    return `<div class="mb-3"><h6>${header} ${meta.length ? '<small class="text-muted">(' + meta.join(" | ") + ')</small>' : ''}</h6>${content}</div>`;
                }).join("<hr>");
                loadHistory();
            } else {
                resultsDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        } catch (err) {
            resultsDiv.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
        }
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Run Comparison';
    });

    function escapeHtml(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    async function loadHistory() {
        try {
            const res = await fetch("/api/compare/history");
            const data = await res.json();
            if (data.ok && data.runs.length > 0) {
                historyBody.innerHTML = data.runs.map(r =>
                    `<tr><td>#${r.id}</td><td>${r.recording_name}</td><td><span class="badge bg-info">${r.run_type}</span></td><td>${r.created_at}</td></tr>`
                ).join("");
            } else {
                historyBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No comparisons yet.</td></tr>';
            }
        } catch (e) {
            historyBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Failed to load history.</td></tr>';
        }
    }
    loadHistory();
})();
</script>
{% endblock %}
```

- [ ] **Step 7: Register compare API and web routers**

In `src/app/api/api.py`, add:

```python
from .endpoints import compare
```

And:

```python
router.include_router(compare.router, prefix="/compare")
```

In `src/app/router.py`, add:

```python
from app.web.compare import router as compare_router
```

And:

```python
router.include_router(compare_router, prefix="")
```

- [ ] **Step 8: Add compare link to sidebar**

In `src/templates/base.html`, add after the Stats sidebar item:

```html
                        <li class="nav-item">
                            <a href="/compare" class="nav-link {{ 'active' if active_page == 'compare' }}">
                                <i class="nav-icon bi bi-columns-gap"></i>
                                <p>Compare</p>
                            </a>
                        </li>
```

- [ ] **Step 9: Commit**

```bash
git add src/services/ModelRegistry.py src/app/api/endpoints/compare.py src/app/web/compare.py src/templates/compare.html src/app/api/api.py src/app/router.py src/templates/base.html src/app/depends.py src/repositories/SqliteDBRepository.py
git commit -m "feat: add model comparison lab with side-by-side transcription/summarization"
```

---

## Task 10: Historical Cost Estimation Script

**Files:**
- Create: `scripts/estimate_historical_costs.py`

- [ ] **Step 1: Create the estimation script**

Create `scripts/estimate_historical_costs.py`:

```python
"""
One-time script to estimate historical API costs for existing recordings.
Retroactively populates the cost_tracking table with estimated costs.

Usage: python scripts/estimate_historical_costs.py
"""
import os
import sys
import sqlite3

# Add src to path so we can import project modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Gemini pricing estimates (per 1M tokens)
GEMINI_INPUT_RATE = 0.075 / 1_000_000   # $0.075 per 1M input tokens (Flash)
GEMINI_OUTPUT_RATE = 0.30 / 1_000_000   # $0.30 per 1M output tokens (Flash)

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def main():
    db_name = os.getenv("DATABASE_NAME", "agendino.db")
    db_path = os.path.join(os.path.dirname(__file__), "..", "settings", db_name)

    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get all recordings with transcripts
    recordings = conn.execute(
        "SELECT id, name, transcript, duration FROM recording WHERE transcript IS NOT NULL AND transcript != ''"
    ).fetchall()

    print(f"Found {len(recordings)} recordings with transcripts")

    inserted = 0
    skipped = 0

    for rec in recordings:
        # Check if cost data already exists for this recording
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM cost_tracking WHERE recording_id = ?", (rec["id"],)
        ).fetchone()

        if existing["cnt"] > 0:
            skipped += 1
            continue

        # Estimate transcription cost (assumed Gemini was used)
        transcript = rec["transcript"]
        input_tokens = estimate_tokens(transcript)
        transcription_cost = input_tokens * GEMINI_INPUT_RATE

        conn.execute(
            """INSERT INTO cost_tracking
               (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
               VALUES (?, 'transcription', 'gemini', 'gemini-flash', ?, 0, ?, 1)""",
            (rec["id"], input_tokens, round(transcription_cost, 6)),
        )
        inserted += 1

        # Check for summaries
        summaries = conn.execute(
            "SELECT id, summary FROM summary WHERE recording_id = ?", (rec["id"],)
        ).fetchall()

        for s in summaries:
            if not s["summary"]:
                continue
            # Estimate: input = transcript tokens, output = summary tokens
            in_tokens = estimate_tokens(transcript)
            out_tokens = estimate_tokens(s["summary"])
            cost = (in_tokens * GEMINI_INPUT_RATE) + (out_tokens * GEMINI_OUTPUT_RATE)

            conn.execute(
                """INSERT INTO cost_tracking
                   (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
                   VALUES (?, 'summarization', 'gemini', 'gemini-flash', ?, ?, ?, 1)""",
                (rec["id"], in_tokens, out_tokens, round(cost, 6)),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"Done. Inserted {inserted} estimated cost entries, skipped {skipped} recordings (already had data).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/estimate_historical_costs.py
git commit -m "feat: add historical cost estimation script for existing recordings"
```

---

## Task 11: Environment + Cleanup

**Files:**
- Modify: `.env` (add new vars, remove old)
- Verify: app starts and all pages render

- [ ] **Step 1: Update .env with new variables**

Add to `.env`:

```
DEEPGRAM_API_KEY=
OBSIDIAN_VAULT_PATH=
```

Remove from `.env`:

```
NOTION_API_KEY=...
NOTION_PAGE_ID=...
```

- [ ] **Step 2: Verify app starts**

Run: `cd src && python -m uvicorn app.main:app --reload`

Expected: Server starts without import errors.

- [ ] **Step 3: Verify each page loads**

- `GET /` — Dashboard loads, transcription dropdown shows "Deepgram Nova" and "Whisper (local)"
- `GET /stats` — Stats page loads, shows empty state or estimated costs
- `GET /compare` — Compare page loads, recording dropdown populated, engine checkboxes shown
- `GET /knowledge` — Knowledge page still works (unchanged)
- `GET /calendar` — Calendar page still works (unchanged)

- [ ] **Step 4: Test core flows**

- Upload a recording → transcribe with Deepgram → verify transcript appears
- Summarize → verify summary appears
- Check `/stats` → verify cost entry appears
- Run a transcription comparison on `/compare` → verify side-by-side results

- [ ] **Step 5: Commit .env changes**

```bash
git add .env
git commit -m "chore: update env vars — add Deepgram/Obsidian, remove Notion"
```

---

## Dependency Graph

```
Task 1 (schema) ──────┬──→ Task 2 (CostMetadata + CostRepo)
                       │
                       ├──→ Task 3 (Deepgram service) ──┐
                       │                                  │
                       ├──→ Task 4 (Obsidian service) ──┤
                       │                                  │
                       └──→ Task 7 (markdown prompts)   │
                                                          │
                        Task 2 + 3 + 4 ──→ Task 5 (wiring DI + controller)
                                                          │
                                            Task 5 ──→ Task 6 (frontend UI)
                                                          │
                        Task 1 + 2 ──→ Task 8 (stats dashboard)
                                                          │
                        Task 1 + 2 + 3 + 5 ──→ Task 9 (compare lab)
                                                          │
                        Task 1 + 2 ──→ Task 10 (historical estimation)
                                                          │
                        All ──→ Task 11 (env + verification)
```

**Parallelizable groups:**
- **Group A** (after Task 1): Tasks 2, 3, 4, 7 can run in parallel
- **Group B** (after Group A): Task 5 (requires 2, 3, 4)
- **Group C** (after Task 5): Tasks 6, 8, 9, 10 can run in parallel
- **Group D**: Task 11 (final verification)
