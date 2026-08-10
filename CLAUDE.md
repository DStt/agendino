# CLAUDE.md

Guidance for working in this repo. Read this before making changes.

## What AgenDino is

A self-hosted web dashboard for managing, transcribing, summarizing, and extracting tasks from
audio recordings (originally from HiDock USB devices). Stack: **FastAPI** (web) + **Celery/Redis**
(background jobs) + **Traefik** (TLS reverse proxy) + **SQLite** (data) + **ChromaDB** (RAG vector
store). AI via **Google Gemini** (transcription/summarization/RAG/recaps), **local Whisper**
(faster-whisper), and optionally **Claude** (summarization only).

## Layout

```
src/
  main.py                  FastAPI app (mounts /static, optional AuthMiddleware, router)
  app/
    depends.py             Dependency wiring + config (get_config, get_*_service/controller)
    api/endpoints/         Route handlers (dashboard.py is the big one)
    auth_middleware.py     Session-cookie gate (when AUTH_ENABLED)
  controllers/             Orchestration (DashboardController, Calendar, RAG, Proactor)
  services/                One concern each: TranscriptionService (Gemini), WhisperTranscriptionService,
                           SummarizationService (Gemini) / ClaudeSummarizationService, TaskGenerationService,
                           DailyRecapService, RAGService, NotionService, AuthService, ICalSyncService
  repositories/            SqliteDBRepository, LocalRecordingsRepository, VectorStoreRepository (ChromaDB),
                           SystemPromptsRepository
  celery_tasks.py          transcribe/summarize/generate tasks (DatabaseTask base)
  celery_config.py         Celery app (Redis broker/backend)
  task_locks.py            Redis dedup locks for long-running ops
  static/ , templates/     Vanilla JS + Jinja2 (no frontend build step)
settings/                  db_init.sql, agendino.db, vector_store/, hf_cache/  (runtime data; gitignored except db_init.sql)
local_recordings/          audio files
system_prompts/            summarization prompt templates (baked into image)
certs/                     TLS cert/key for Traefik (contents gitignored)
```

Flow: endpoint → controller → service/repository. Heavy AI work is **deferred to Celery**, not run
in the request.

## Commands

- **Configure:** `cp .env.example .env` then set `GEMINI_API_KEY` (and any others). Every variable is
  documented in `.env.example`.
- **Local dev:** `cd src && fastapi dev main.py` (serves on :8000). Background jobs also need Redis +
  a worker: `cd src && celery -A celery_tasks worker --loglevel=info` (see `CELERY_GUIDE.md`).
- **Docker:** `docker compose up -d --build`. GPU Whisper: set `GPU=1` in `.env` (or
  `docker compose -f compose.yaml -f compose.gpu.yaml up -d`). See `docs/docker.md`.
- **Tests:** `pytest` (from repo root; config in `pytest.ini`).
- **Lint:** `flake8` (config in `.flake8`; CI runs `style.yml`). Tests run in `tests.yml`.

## Config & dependency injection (important, non-obvious)

- `depends.py::get_config()` snapshots `os.environ` into a dict **once**. Many vars are read with
  `_config["KEY"]` — **required**, raising `KeyError` if absent: `GEMINI_API_KEY`, `GEMINI_MODEL`,
  `GEMINI_EMBEDDING_MODEL`, `DATABASE_NAME`, `NOTION_API_KEY`, `NOTION_PAGE_ID`. A `.env` missing any
  of these crashes the dashboard controller build. `WHISPER_*` use `.get(..., default)` (optional).
  → When adding config, prefer `.get("KEY", default)` unless it's genuinely required, and add it to
  `.env.example`.
- **Per-task model override:** transcription uses `GEMINI_TRANSCRIPTION_MODEL` falling back to
  `GEMINI_MODEL`; the other Gemini tasks use `GEMINI_MODEL`.
- **`.env` reaches containers via `env_file:`, not the image.** `.dockerignore` excludes `.env`, so
  `compose.yaml` injects it at runtime with `env_file: - .env` on `agendino` and `celery`. Local
  (non-Docker) runs read `.env` via `load_dotenv()`.

## Compose / deployment specifics

- **Precedence:** Compose `environment:` overrides `env_file:`. The `celery` service hardcodes
  `WHISPER_DEVICE=auto`, so `.env`'s `WHISPER_DEVICE` is ignored in Docker — `GPU=1` is the real
  toggle (`auto` resolves to CUDA only when a GPU is reserved via `compose.gpu.yaml`).
- **`$$` in commands:** `--workers $${WEB_CONCURRENCY:-4}` / `--concurrency=$${CELERY_CONCURRENCY:-1}`
  use `$$` so Compose doesn't consume the var at parse time — the container shell expands it from the
  env injected on the same service. `WEB_CONCURRENCY` also drives the dashboard's parallel upload
  limit (rendered into the page).
- **`INTERNAL_IP`** is substituted into Traefik `Host(...)` rules (app + dashboard). It must match how
  you reach the server or Traefik 404s; default `127.0.0.1` is localhost-only.
- **`COMPOSE_FILE` separator** is `:` on Linux, `;` on Windows. GPU runs only on the `celery` worker
  and is Linux-targeted (needs NVIDIA Container Toolkit). `float16` needs GPU compute capability ≥ 7.0.
- **Image:** Dockerfile is CUDA-based (runs CPU too); paths are repo-relative (`./settings`,
  `./local_recordings`, `./certs`).

## Background jobs & polling

- Transcribe / summarize / generate run as Celery tasks. The API acquires a **Redis lock**
  (`task_locks.py`) before enqueueing so duplicate requests don't double-run; the worker releases it
  in `DatabaseTask.after_return` (TTL is a crash safety net). Lock keys: `lock:transcribe:{name}`,
  `lock:summarize:{name}:{prompt_id}`, `lock:generate:{summary_id}`.
- The frontend polls `GET /tasks/status/{task_id}`. On page refresh it recovers in-flight tasks from
  `GET /tasks/active` (scans the Redis locks) and resumes polling — driven from `loadDashboard()` in
  `static/dashboard.js`; `_activePolls` dedups poll loops. Row indicators: "Transcribing…" (from the
  persisted `transcription_status` column) and "Summarizing…" (from `/tasks/active`).

## Data model (SQLite)

`recording` (has `transcript`, `transcription_status`) → `summary` (FK `ON DELETE CASCADE`) →
`task` (FK `ON DELETE CASCADE`). Plus calendar/event/recap tables. `_connect()` sets
`PRAGMA foreign_keys = ON`, WAL journal mode, and a busy timeout. Summaries are embedded in ChromaDB
(`VectorStoreRepository`); embeddings are **not** auto-cleaned when a recording is deleted (known gap),
though `delete_transcript` does clean them.

## Knowledge base (RAG) providers

Both RAG AI calls are provider-toggleable (mirrors `SUMMARIZATION_PROVIDER`), default Gemini.
Embedder classes live in `repositories/embedders.py`; all expose `embed(texts)` + an `id` (used as the
collection stamp). Wired in `depends.py` (`get_embedder`, `get_rag_service`); `RAGController` is
provider-agnostic.
- **`EMBEDDING_PROVIDER`** = `gemini` | `ollama` | `local`:
  - `ollama` (Docker default) — `OllamaEmbedder` calls the **dockerized Ollama** container's **native
    `/api/embed`** (not OpenAI `/v1/embeddings`) so it can pass `num_batch=8192`: embedding models
    process the whole input in one batch, so a long summary needs `num_batch ≥ its token count` or it
    errors ("input … too large to process"). One shared model for all web workers
    (`OLLAMA_EMBEDDING_MODEL`, default `bge-m3`); inputs over 8192 tokens are truncated to context.
  - `local` — in-process `LocalEmbedder` (sentence-transformers, lazy-loaded like Whisper). Loads one
    model **per uvicorn worker**; for non-Docker dev (`sentence-transformers` is **not** in
    `requirements.txt` — pip install it). Use a **long-context** model (`bge-m3`, 8192 ctx).
  - `gemini` — cloud.
- **`RAG_PROVIDER`** = `gemini` | `ollama` | `local`. `ollama` (Docker) and `local` (non-Docker host
  Ollama) are **synonyms** → `OllamaRAGService` (Ollama's OpenAI-compatible `/v1/chat/completions` via
  `httpx`, `OLLAMA_MODEL`). **Unset → follows `EMBEDDING_PROVIDER`**: Ollama generation when
  embeddings are `ollama`, else Gemini.
- **`get_embedder()` is a process-level singleton; `get_vector_store_repository()` is NOT** — a cached
  ChromaDB collection handle goes stale across the reset's delete/recreate (caused
  `hnsw segment reader: Nothing found on disk`).
- **Mismatch reset:** `VectorStoreRepository` stamps the collection with the embedder id and
  **auto-clears on startup** if it changed (embeddings of different models/dims aren't interchangeable).
  Safe — summaries live in SQLite; reload from the Knowledge page. `get_stats()` derives `needs_reload`
  as `total_summaries > 0 and loaded_count == 0`.
- **Docker/GPU:** the `ollama` service (in `compose.yaml`) serves embeddings + generation; models
  bind-mount to `settings/ollama_models`. `GPU=1` (`compose.gpu.yaml`) reserves the GPU for `ollama`
  and `celery`/Whisper — **not** `agendino` (with Ollama embeddings the web service loads no model).
  No cross-container GPU queue → VRAM is additive; mind the budget on small cards.
- **AI mind map** (`RAGController.generate_mind_map`) reads from the **vector store** and, above
  `MIN_CLUSTER_N` summaries, **clusters embeddings** (`sklearn.cluster.KMeans` on L2-normalized vectors
  = cosine; adaptive `k≈√(n/2)`) and asks the LLM to label one branch per cluster (`label_cluster`) —
  avoids overflowing the model context at scale. Re-clusters each run; small corpora fall back to the
  single-shot `generate_mind_map`.
- **Auto-embed on summarize:** `DashboardController.summarize_recording` embeds each new summary
  best-effort (`build_summary_document` in `VectorStoreRepository`, shared with `load_summaries`) so
  `/ask` + the mind map see it without a manual reload. "Load summaries" remains for backfill/repair.
- **`/ask` context:** `build_rag_context` caps each doc (`RAG_DOC_CHAR_CAP`) and `OLLAMA_CONTEXT_LENGTH`
  is raised so the top-k retrieved summaries fit the window instead of being clipped.

## Conventions & gotchas

- **Vanilla JS frontend, no build.** Top-level functions in `static/dashboard.js` (`loadDashboard`,
  `actionButtons`, polling helpers) are module scope; UI handlers live in the `DOMContentLoaded`
  block. **Bump `dashboard.js?v=N` in `templates/dashboard/home.html`** when you change the JS, or
  browsers cache the old file.
- **FastAPI route ordering:** literal paths must be declared **before** param paths — e.g.
  `/tasks/active` and `/tasks/status/{id}` come before `/tasks/{summary_id}`.
- **Speaker labels:** transcripts use `[MM:SS] Speaker N:` lines; the speaker-rename UI parses that
  format. Gemini transcription does diarization; local Whisper does not.
- **flake8:** keep module-level code (e.g. `logger = logging.getLogger(__name__)`) below imports
  (E402); the style CI will fail otherwise.
- **Secrets:** `.env` is gitignored; `certs/*` is gitignored except `.gitkeep`; `__pycache__/`/`*.pyc`
  ignored. Never commit API keys or TLS private keys. `.env.example` holds placeholders only.
- Commit/push only when asked; default branch is `master`.
