"""
Redis-backed locks that prevent the same long-running operation (transcription,
summarization, task generation) from being queued and processed more than once
concurrently across Celery workers.

The lock value is the Celery task_id of the in-flight task. A second request for
the same unit of work fails to acquire the lock and instead receives the existing
task_id so the frontend can poll the already-running task rather than starting a
duplicate.

Locks are acquired by the API (before enqueue) and released by the worker (after
the task returns, via DatabaseTask.after_return). The TTL is only a safety net so a
crashed worker cannot deadlock a recording forever.
"""
import logging
import os

import redis

logger = logging.getLogger(__name__)

# Safety-net TTL: a little longer than the hard task time limit (30 min) so a worker
# that dies mid-task eventually frees the lock on its own.
LOCK_TTL_SECONDS = int(os.getenv("TASK_LOCK_TTL", str(31 * 60)))

_redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(_redis_url, decode_responses=True)
    return _client


# ─── Key builders ────────────────────────────────────────────────

def transcribe_lock_key(name: str) -> str:
    return f"lock:transcribe:{name}"


def summarize_lock_key(name: str, prompt_id: str) -> str:
    return f"lock:summarize:{name}:{prompt_id}"


def generate_lock_key(summary_id: int) -> str:
    return f"lock:generate:{summary_id}"


# ─── Lock operations ─────────────────────────────────────────────

def acquire(key: str, task_id: str, ttl: int = LOCK_TTL_SECONDS) -> bool:
    """Atomically claim the lock for task_id. Returns True if acquired."""
    return bool(_redis().set(key, task_id, nx=True, ex=ttl))


def current_holder(key: str) -> str | None:
    """Return the task_id currently holding the lock, or None."""
    return _redis().get(key)


def list_active() -> list[dict]:
    """Return all in-flight task locks as [{"key": <lock key>, "task_id": <id>}].

    Lets the frontend resume polling running tasks after a page refresh.
    """
    client = _redis()
    active = []
    for key in client.scan_iter(match="lock:*"):
        task_id = client.get(key)
        if task_id:
            active.append({"key": key, "task_id": task_id})
    return active


def release(key: str) -> None:
    """Release the lock. Safe to call even if the key is already gone."""
    try:
        _redis().delete(key)
    except Exception as e:  # never let cleanup failure mask the task result
        logger.warning(f"Failed to release task lock {key}: {e}")
