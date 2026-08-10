# Celery Task Queue Integration - Implementation Guide

## Overview

This document explains the Celery task queue implementation for Agendino, which enables long-running operations (transcription, summarization, task generation) to work reliably across multiple uvicorn worker processes.

## Problem Solved

**Before**: Transcription and summarization requests blocked HTTP responses and couldn't persist across worker restarts.

**After**: Long-running tasks are queued in Redis and can be processed by any available worker. Frontend polls for progress.

## Architecture

```
┌─────────────┐
│   Browser   │ 1. POST /api/dashboard/transcribe/file.mp3
└──────┬──────┘    Returns: {task_id: "abc123", status: "queued"}
       │
       │ 2. Poll GET /api/dashboard/tasks/status/abc123 every 5s
       ▼
┌──────────────────────────────────────────────────────────┐
│            FastAPI (Port 8000)                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Endpoint: POST /transcribe/{name}                   │ │
│  │ Action: Launch task & return {task_id, status}     │ │
│  └─────────────────────────────────────────────────────┘ │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Endpoint: GET /tasks/status/{task_id}              │ │
│  │ Action: Check Redis for task result & return status│ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
       │
       │ (via Redis)
       ▼
┌──────────────────────────────────────────────────────────┐
│            Redis (Port 6379)                             │
│  - Task Queue (FIFO)                                     │
│  - Task Results (key-value store)                        │
│  - Auto-expires results after 1 hour                     │
└──────────────────────────────────────────────────────────┘
       │
       │ (picks up from queue)
       ▼
┌──────────────────────────────────────────────────────────┐
│            Celery Worker (Background Process)            │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ transcribe_audio_task()                             │ │
│  │ summarize_audio_task()                              │ │
│  │ generate_tasks_task()                               │ │
│  │                                                      │ │
│  │ Processes: Transcription, Summarization, Tasks      │ │
│  │ Updates: Results saved back to Redis                │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## Installation & Setup

### 1. Install Dependencies

Dependencies have been added to `requirements.txt`:

```bash
cd agendino
pip install -r requirements.txt
```

This installs:

- `celery[redis]` - Task queue framework
- `redis` - Redis Python client

### 2. Install & Run Redis

**On Linux/Mac:**

```bash
# Homebrew (Mac)
brew install redis
redis-server

# Or with package manager (Linux)
sudo apt-get install redis-server
redis-server
```

**On Docker:**

```bash
docker run -p 6379:6379 redis:7-alpine
```

**On Windows:**

- Use Windows Subsystem for Linux (WSL) + Linux instructions
- Or use Docker Desktop + above command

### 3. Start the Services

**Terminal 1 - Redis:**

```bash
redis-server
# Should show: "Ready to accept connections"
```

**Terminal 2 - Celery Worker:**

```bash
cd src
celery -A celery_tasks worker --loglevel=info
# Should show: "mingle starting with max concurrency 8"
```

**Terminal 3 - FastAPI App:**

```bash
cd src
uvicorn main:app --reload
# Should show: "Uvicorn running on http://0.0.0.0:8000"
```

Visit: http://localhost:8000

## API Changes

### Modified Endpoints

#### Transcription

```
POST /api/dashboard/transcribe/{name}
Body: {"engine": "gemini" or "whisper"}

OLD Response:
{
  "ok": true,
  "transcript": "...",
  "cached": false
}

NEW Response (if queued):
{
  "ok": true,
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "queued",
  "message": "Transcription task queued: 4f2e5c8a..."
}

NEW Response (if already running — see "Duplicate Prevention" below):
{
  "ok": true,
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "already_running",
  "message": "Transcription already in progress"
}

NEW Response (if cached):
{
  "ok": true,
  "transcript": "...",
  "cached": true
}
```

#### Summarization

```
POST /api/dashboard/summarize/{name}
Body: {"prompt_id": "prompt-id"}

OLD Response:
{
  "ok": true,
  "summary_id": 123,
  "message": "..."
}

NEW Response:
{
  "ok": true,
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "queued",
  "message": "Summarization task queued: 4f2e5c8a..."
}
```

#### Task Generation

```
POST /api/dashboard/tasks/generate
Body: {"summary_id": 123}

OLD Response:
{
  "ok": true,
  "tasks_count": 5,
  "message": "..."
}

NEW Response:
{
  "ok": true,
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "queued",
  "message": "Task generation queued: 4f2e5c8a..."
}
```

### New Endpoints

#### Get Task Status

```
GET /api/dashboard/tasks/status/{task_id}

Response (Queued/Pending):
{
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "PENDING"
}

Response (In Progress):
{
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "PROGRESS",
  "meta": {"status": "transcribing"}
}

Response (Completed):
{
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "SUCCESS",
  "result": {
    "ok": true,
    "transcript": "...",
    "cached": false
  }
}

Response (Failed):
{
  "task_id": "4f2e5c8a-9b1d-4c3e-8f5a-2d1e9c7f4a3b",
  "status": "FAILURE",
  "error": "File not found: recording.mp3"
}
```

**Note:** Task results expire automatically from Redis after 1 hour
(`result_expires=3600` in `celery_config.py`). The `PROGRESS` response also includes
a `meta` field (e.g. `{"status": "transcribing"}`) while the task is running.

#### Cancel Task

```
DELETE /api/dashboard/tasks/status/{task_id}

Response:
{
  "ok": true,
  "message": "Task 4f2e5c8a-... revoked"
}
```

> The cancel route lives under `/tasks/status/{task_id}` (not `/tasks/{task_id}`) so it
> does not collide with the existing `DELETE /tasks/{task_id}` route that deletes a
> generated task by its DB id. Cancellation uses `revoke(terminate=True)`, which kills
> the worker process — so the worker's lock-release hook may not run; the in-flight lock
> (see below) then expires on its own via its TTL.

## Duplicate Prevention (across workers)

Queueing alone does not stop the **same** file from being transcribed twice: until a
transcript is saved, a second request (double-click, second tab, or another worker)
would otherwise enqueue a duplicate task and both workers would do the same work. Two
mechanisms prevent this:

### 1. Redis in-flight lock (authoritative, cross-worker)

- `src/task_locks.py` holds a Redis key per unit of work whose **value is the Celery
  `task_id`** of the in-flight task:
  - `lock:transcribe:{name}`
  - `lock:summarize:{name}:{prompt_id}`
  - `lock:generate:{summary_id}`
- The API claims the lock with `SET key task_id NX EX <ttl>` **before** queueing:
  - **Acquired** → enqueue with that `task_id`, return `{status: "queued"}`.
  - **Not acquired** → read the existing value and return
    `{status: "already_running", task_id: <existing>}` so the frontend polls the
    task that is already running instead of starting a new one.
- The **worker** releases the lock in `DatabaseTask.after_return` (so the lock spans
  the whole run, even across the API and worker containers). The TTL
  (`TASK_LOCK_TTL`, default 31 min — just over the 30 min hard task limit) is only a
  safety net so a crashed/terminated worker cannot deadlock a file forever.

### 2. `transcription_status` DB column (durable, drives UI)

- A migration-safe `transcription_status` column on `recording`
  (`idle → queued → running → done → failed`) added in `SqliteDBRepository`.
- Set to `queued` by the endpoint at enqueue time, `running` at the start of the
  transcription task, `done` on success, and `failed` on terminal failure
  (`after_return`).
- Exposed via `GET /api/dashboard/recordings` (`transcription_status` per recording)
  so the dashboard can show a status badge. Unlike the Redis lock, it survives a
  Redis flush or restart.

> Edge case: cancelling a task with `terminate=True` kills the worker before
> `after_return` runs, so the lock waits for its TTL and the DB row may remain
> `running` until then.

## Frontend Changes

The JavaScript frontend now:

1. **Sends requests as before** - No change to UI or user experience
2. **Receives task_id** - If transcription/summarization is queued
3. **Polls status** - Every 5 seconds via `GET /api/dashboard/tasks/status/{task_id}`
4. **Displays results** - When task completes (status="SUCCESS")
5. **Shows errors** - If task fails (status="FAILURE") or times out

### Polling Configuration

In `dashboard.js`:

```javascript
// Poll every 5 seconds
await new Promise(resolve => setTimeout(resolve, 5000));

// Max 720 attempts = 1 hour timeout
while (attempts < maxAttempts)
```

You can adjust these values if needed.

## Scaling

### Add More Workers

To process tasks faster, add more Celery workers:

```bash
# Terminal 4
cd src
celery -A celery_tasks worker --loglevel=info --concurrency=4

# Terminal 5
cd src
celery -A celery_tasks worker --loglevel=info --concurrency=4
```

Now you have 3 workers processing tasks in parallel!

### Multi-Machine Setup

On different machines:

```bash
# Machine 2
export CELERY_BROKER_URL=redis://redis-server-ip:6379/0
celery -A celery_tasks worker --loglevel=info

# Machine 3
export CELERY_BROKER_URL=redis://redis-server-ip:6379/0
celery -A celery_tasks worker --loglevel=info
```

### Docker Compose

`compose.yaml` already wires this up: a `redis` service, a `celery` worker service
(`working_dir: /app/src`; worker concurrency set via the `CELERY_CONCURRENCY` env var,
default `1` — see [Docker → Concurrency tuning](docs/docker.md)), and `CELERY_BROKER_URL`
+ `depends_on: redis` on the `agendino` API service. Just `docker compose up --build`.

> Important: the `celery` and `agendino` services must mount the **same** host
> directories for `/app/local_recordings` and `/app/settings` (the SQLite DB lives
> under `settings/`). The worker writes results that the API later reads, so they
> must share that state.

To run more workers in parallel:

```bash
docker compose up --build --scale celery=3
```

## Task Cleanup & Monitoring

### Manual Task Cleanup

If tasks accumulate, you can clear them:

```python
# Python script
from celery_config import celery_app
import redis

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Clear all tasks
r.flushdb()

# Or clear specific keys
r.delete('celery')
```

### Monitor Tasks

```bash
# Real-time task monitoring
celery -A celery_tasks events

# Or use a web UI
pip install flower
celery -A celery_tasks flower
# Visit http://localhost:5555
```

## Configuration

Edit `src/celery_config.py` to customize:

```python
celery_app.conf.update(
    # Redis broker URL
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",

    # Task settings
    task_serializer="json",
    result_serializer="json",

    # Time limits (in seconds)
    task_soft_time_limit=25 * 60,    # 25 minutes
    task_time_limit=30 * 60,         # 30 minutes (hard limit)

    # Result expiry
    result_expires=3600,              # 1 hour
)
```

## Troubleshooting

### Issue: "Connection refused" error

```
Error: Cannot connect to redis://localhost:6379/0
```

**Solution:** Start Redis server in a separate terminal

### Issue: Celery worker not processing tasks

```
[ERROR/MainProcess] consumer: ERROR in Consumer callback
```

**Solution:** Check Redis connection and restart worker

### Issue: Tasks stuck as "PENDING"

```
Status: "PENDING" (never changes)
```

**Solution:** Ensure Celery worker is running (`celery -A celery_tasks worker`)

### Issue: Tasks timeout

```
Status: "FAILURE", Error: "Task timed out"
```

**Solution:** Increase time limits in `celery_config.py`, or optimize transcription code

## Performance Tips

1. **Use Concurrency**: Set `--concurrency` to match CPU cores

   ```bash
   celery -A celery_tasks worker --loglevel=info --concurrency=8
   ```

2. **Use Multiple Workers**: Run on different machines for load distribution

3. **Monitor with Flower**:

   ```bash
   celery -A celery_tasks flower --port=5555
   ```

4. **Optimize Transcription**: Use local Whisper instead of cloud Gemini for speed

## Files Modified

- `requirements.txt` - Added celery[redis] and redis
- `compose.yaml` - Added `redis` + `celery` worker services; `CELERY_BROKER_URL` + `depends_on` on `agendino`
- `src/celery_config.py` - **NEW** - Celery configuration
- `src/celery_tasks.py` - **NEW** - Task definitions; builds the controller via `app.depends`; releases locks and updates status in `after_return`
- `src/task_locks.py` - **NEW** - Redis in-flight locks for duplicate prevention
- `src/app/api/endpoints/dashboard.py` - transcribe/summarize/tasks-generate now enqueue Celery tasks behind a Redis lock; added `GET`/`DELETE /tasks/status/{task_id}`
- `src/controllers/DashboardController.py` - Added `bare_name`, `get_cached_transcript`, `set_transcription_status`; `transcription_status` in `get_recordings_status`
- `src/repositories/SqliteDBRepository.py` - `transcription_status` column migration + `set_transcription_status`
- `src/models/DBRecording.py` - `transcription_status` field
- `src/static/dashboard.js` - `pollTaskStatus()` helper; transcribe/summarize/generate handlers poll for completion instead of blocking

## References

- Celery Documentation: https://docs.celeryproject.org/
- Redis Documentation: https://redis.io/documentation
- FastAPI Background Tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
