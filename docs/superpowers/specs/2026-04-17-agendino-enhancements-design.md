# AgenDino Enhancements — Design Spec

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Deepgram transcription, cost tracking, Obsidian export, stats dashboard, markdown prompts, model comparison lab

---

## 1. Deepgram Transcription Engine

### Goal
Replace Gemini cloud transcription with Deepgram Nova. Gemini lacks competitive speed and cost for transcription, and Deepgram provides native speaker diarization — eliminating the need for post-processing.

### Changes

**New file:** `src/services/DeepgramTranscriptionService.py`
- Uses Deepgram Python SDK (`deepgram-sdk`)
- Calls Nova model with diarization enabled
- Returns formatted output matching current convention: `[MM:SS] Speaker N: text`
- Returns cost metadata alongside transcript (audio minutes, model used, cost USD)

**Deleted file:** `src/services/TranscriptionService.py` (Gemini transcription)

**Modified files:**
- `src/models/dto/TranscribeRequestDTO.py` — `engine` field accepts `"deepgram"` (default) or `"whisper"`
- `src/controllers/DashboardController.py` — route to `DeepgramTranscriptionService` instead of `TranscriptionService`
- `src/app/depends.py` — inject `DeepgramTranscriptionService`, read `DEEPGRAM_API_KEY` from env
- UI templates — update engine dropdown: Gemini → Deepgram

**Environment:**
- New: `DEEPGRAM_API_KEY`
- Removed from transcription usage: `GEMINI_API_KEY` (still used by summarization/RAG/etc.)

### Output Format
Deepgram returns word-level timestamps and speaker labels. Service formats to:
```
[00:15] Speaker 1: Hey, how's the project going?
[00:18] Speaker 2: Good, we finished the API yesterday.
```

Speaker renaming in the UI continues to work unchanged — it operates on the formatted text.

### Whisper Local Engine
Unchanged. `WhisperTranscriptionService.py` remains as the fully offline option.

---

## 2. Cost Tracking

### Goal
Track API costs per operation per recording. Show in UI and include in Obsidian exports. Retroactively estimate costs for existing recordings.

### Database Schema

New table in `settings/db_init.sql`:

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`operation` values:** `transcription`, `summarization`, `task_generation`, `daily_recap`, `rag_query`, `embedding`

**`engine` values:** `deepgram`, `whisper`, `gemini`

### Cost Metadata Dataclass

```python
@dataclass
class CostMetadata:
    operation: str
    engine: str
    model: str
    input_units: float    # audio minutes or input tokens
    output_units: float   # output tokens (0 for transcription)
    cost_usd: float
```

Each service method returns `tuple[result, CostMetadata]`. Controllers persist the metadata via repository after each operation.

### Cost Calculation

**Deepgram transcription:** `audio_duration_minutes * rate_per_minute` (rate configurable, default $0.0043/min for Nova pay-as-you-go)

**Gemini LLM calls:** Extract `usage_metadata` from Gemini API response — `prompt_token_count`, `candidates_token_count`. Calculate cost from published per-token rates for the configured model.

**Whisper local:** `cost_usd = 0.0`, track `processing_time_seconds` as metadata.

### Retroactive Estimation

One-time migration script (`scripts/estimate_historical_costs.py`):
- Query all existing recordings with transcripts/summaries
- Transcription estimate: `recording.duration` × Gemini audio rate
- Summarization estimate: `len(transcript)` → approximate token count → Gemini token rate
- Insert rows into `cost_tracking` with `engine = "gemini"` and a flag `estimated = true` (additional boolean column)
- Run manually, idempotent (skips recordings that already have cost data)

### Repository

New `CostTrackingRepository` in `src/repositories/` with methods:
- `save(recording_id, cost_metadata)` — insert row
- `get_by_recording(recording_id)` — all cost entries for a recording
- `get_by_date_range(start, end)` — for stats dashboard
- `get_by_engine()` — aggregated by engine
- `get_totals()` — running totals

---

## 3. Obsidian Export (Replaces Notion)

### Goal
Replace Notion integration with local Obsidian vault export. No API, no paid service — just markdown files written to disk.

### Changes

**New file:** `src/services/ObsidianExportService.py`
- Writes summary as `.md` file to configured vault path
- Creates directory structure matching AgenDino folder hierarchy
- Generates YAML frontmatter with metadata and cost data

**Deleted file:** `src/services/NotionService.py`

**Modified files:**
- `src/controllers/DashboardController.py` — replace Notion publish with Obsidian export
- `src/app/depends.py` — inject `ObsidianExportService`, read `OBSIDIAN_VAULT_PATH`
- UI templates — "Publish to Notion" → "Export to Obsidian"
- API endpoint — update route handler

**Environment:**
- New: `OBSIDIAN_VAULT_PATH`
- Removed: `NOTION_API_KEY`, `NOTION_PAGE_ID`

### File Path Structure

```
{OBSIDIAN_VAULT_PATH}/AgenDino/{folder_path}/{sanitized_title}.md
```

Examples:
- Recording in `Work/Standups` → `vault/AgenDino/Work/Standups/2026-04-17-standup-summary.md`
- Recording in root (no folder) → `vault/AgenDino/2026-04-17-recording-summary.md`

Filename: `{date}-{sanitized-title}.md` — sanitize for filesystem safety (no special chars, max length).

### Frontmatter Format

```yaml
---
title: Standup Summary
tags:
  - standup
  - engineering
date: 2026-04-17
recording: standup-2026-04-17.mp3
duration_seconds: 847
source: agendino
folder: Work/Standups
transcription:
  engine: deepgram
  cost_usd: 0.06
  audio_minutes: 14.1
summarization:
  model: gemini-2.5-flash
  input_tokens: 3200
  output_tokens: 850
  cost_usd: 0.002
total_cost_usd: 0.062
---
```

### Body Content
Summary markdown as-is (already generated in markdown format by Gemini).

### Behavior
- Creates directories if they don't exist
- Overwrites existing file if re-exported (same filename)
- Returns the written file path for UI confirmation

### Dependencies
None — just `pathlib`. Frontmatter generated as a formatted string (no PyYAML dependency needed).

---

## 4. Stats Dashboard

### Goal
Reporting-style dashboard showing API costs, usage counts, and trends.

### New Page: `/stats`

**Template:** `src/templates/stats.html`
**Web handler:** `src/app/web/stats.py`
**API endpoints:** `src/app/api/endpoints/stats.py`

### Dashboard Sections

#### Per-Recording Cost Table
- Sortable table: recording name, date, folder, transcription cost, summarization cost, total cost
- Filter by folder, date range
- Flag estimated vs actual costs

#### Time Period Summaries
- Daily / weekly / monthly spend totals
- Date range picker
- Bar chart visualization (Chart.js loaded from CDN or vendored in `src/static/` — no Python dependency)

#### By-Engine Breakdown
- Pie or bar chart: spend per engine (Deepgram, Gemini, Whisper/free)
- Also by operation type (transcription vs summarization vs task generation vs RAG)

#### Usage Counts
- Total recordings transcribed
- Total summaries generated
- Total tasks extracted
- Total Obsidian exports
- Total RAG queries
- Total comparison runs

#### Running Total
- Cumulative spend over time (line chart)
- Current month spend highlighted

### Data Source
All data from `cost_tracking` table, aggregated via `CostTrackingRepository` methods. Server-side rendered via Jinja2, charts via client-side JS with data passed as JSON in template.

---

## 5. Markdown System Prompts

### Goal
Support `.md` files alongside `.txt` for system prompts.

### Changes

**Modified file:** `src/repositories/SystemPromptsRepository.py`

```python
SUPPORTED_EXTENSIONS = {".txt", ".md"}
```

- `_collect_prompts`: check `prompt_file.suffix in SUPPORTED_EXTENSIONS` instead of `== ".txt"`
- `get_prompt_content`: try `.txt` first, fall back to `.md` if not found
- Prompt ID remains extension-less: `en/General/Meeting` loads `Meeting.txt` or `Meeting.md`
- If both exist for same stem, `.txt` takes precedence

### No Other Changes
Prompt content is plain text regardless of file extension — the format doesn't affect how it's sent to Gemini.

---

## 6. Model Comparison Lab

### Goal
A/B testing page for transcription and summarization quality across engines and models. Stores results and feedback to inform prompt improvements and engine selection. Extensible for future model additions.

### New Page: `/compare`

**Template:** `src/templates/compare.html`
**Web handler:** `src/app/web/compare.py`
**API endpoints:** `src/app/api/endpoints/compare.py`

### Database Schema

Three new tables in `settings/db_init.sql`:

```sql
CREATE TABLE IF NOT EXISTS comparison_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER REFERENCES recording(id) ON DELETE CASCADE,
    run_type TEXT NOT NULL,          -- 'transcription' or 'summarization'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparison_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,            -- 'deepgram', 'whisper', 'gemini', 'groq', etc.
    model TEXT,                      -- specific model identifier
    system_prompt_id TEXT,           -- for summarization comparisons
    output_text TEXT NOT NULL,
    cost_usd REAL DEFAULT 0.0,
    processing_time_ms INTEGER
);

CREATE TABLE IF NOT EXISTS comparison_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES comparison_run(id) ON DELETE CASCADE,
    segment_index INTEGER,           -- which segment/section (null = overall)
    preferred_result_id INTEGER REFERENCES comparison_result(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Transcription Comparison Flow
1. User selects a recording on `/compare`
2. Picks 2+ transcription engines from available registry
3. Clicks "Run Comparison" — each engine transcribes the same audio
4. Results displayed side-by-side with diff highlighting
5. User marks per-segment preferences (which engine was more accurate)
6. Feedback stored for future reference

### Summarization Comparison Flow
1. User selects a recording (must have transcript)
2. Picks 2+ combinations of: model + system prompt
3. Each combination generates a summary from the same transcript
4. Side-by-side display
5. User marks per-section preferences (which captured key points better)
6. Feedback stored

### Engine/Model Registry

New `src/services/ModelRegistry.py`:

```python
@dataclass
class EngineInfo:
    id: str                # 'deepgram', 'whisper', 'gemini'
    name: str              # Display name
    type: str              # 'transcription', 'summarization', 'both'
    service_class: type    # Reference to service class
    available: bool        # Based on whether API key is configured
```

- Registry auto-discovers available engines based on configured env vars
- Comparison page queries registry to show only available options
- Adding a new engine = implement service class + register in registry
- Future engines (Groq LLM, Ollama, etc.) just add entries

### Cost Tracking Integration
Each comparison run logs cost per result to `cost_tracking` table. Comparison costs show up in stats dashboard under a "comparison" operation type.

### Feedback Usage
- View past comparisons and feedback on `/compare` (history tab)
- Aggregate feedback visible on stats dashboard (win rates per engine/model)
- Informs decisions on default engine selection and prompt refinement

---

## 7. Environment Variables Summary

### New
| Variable | Purpose |
|---|---|
| `DEEPGRAM_API_KEY` | Deepgram Nova transcription API key |
| `OBSIDIAN_VAULT_PATH` | Absolute path to Obsidian vault directory |

### Removed
| Variable | Reason |
|---|---|
| `NOTION_API_KEY` | Notion integration removed |
| `NOTION_PAGE_ID` | Notion integration removed |

### Unchanged
| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Still used for summarization, RAG, embeddings, task generation |
| `GEMINI_MODEL` | LLM model selection |
| `GEMINI_EMBEDDING_MODEL` | Embedding model selection |
| `WHISPER_MODEL_SIZE` | Local Whisper model size |
| `WHISPER_DEVICE` | Whisper compute device |
| `WHISPER_COMPUTE_TYPE` | Whisper compute type |
| `DATABASE_NAME` | SQLite database name |
| `AUTH_SECRET_KEY` | Session auth secret |
| `AUTH_ENABLED` | Toggle authentication |

---

## 8. New Dependencies

| Package | Purpose |
|---|---|
| `deepgram-sdk` | Deepgram API client |

No other new dependencies. `NotionService` removal drops the implicit dependency on `httpx` for Notion calls (but `httpx` is still used by iCal sync).

---

## 9. Files Changed Summary

### New Files
- `src/services/DeepgramTranscriptionService.py`
- `src/services/ObsidianExportService.py`
- `src/services/ModelRegistry.py`
- `src/repositories/CostTrackingRepository.py`
- `src/app/api/endpoints/stats.py`
- `src/app/api/endpoints/compare.py`
- `src/app/web/stats.py`
- `src/app/web/compare.py`
- `src/templates/stats.html`
- `src/templates/compare.html`
- `src/models/dto/CostMetadata.py`
- `scripts/estimate_historical_costs.py`

### Deleted Files
- `src/services/TranscriptionService.py`
- `src/services/NotionService.py`

### Modified Files
- `src/models/dto/TranscribeRequestDTO.py` — engine values
- `src/controllers/DashboardController.py` — Deepgram routing, cost tracking, Obsidian export
- `src/app/depends.py` — new service injection, new env vars
- `src/app/router.py` — new routes for stats + compare
- `src/repositories/SystemPromptsRepository.py` — .md support
- `src/repositories/SqliteDBRepository.py` — cost tracking queries (or new repo)
- `settings/db_init.sql` — new tables
- `requirements.txt` — add deepgram-sdk
- `.env` — new vars, remove Notion vars
- UI templates (dashboard) — engine dropdown, export button text

---

## 10. What's NOT Changing

- Gemini for summarization, task generation, daily recaps, RAG Q&A, embeddings, mind maps
- Whisper local transcription engine
- Authentication system
- Calendar sync (iCal)
- Recording management (upload, folders, playback)
- Speaker renaming in transcripts
- System prompt content and structure (just loader accepts .md now)
- ChromaDB vector store
- All existing API endpoints (except Notion publish → Obsidian export)
