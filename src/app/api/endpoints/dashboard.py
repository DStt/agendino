import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

import task_locks
from app import depends
from celery_config import celery_app
from celery_tasks import generate_tasks_task, summarize_audio_task, transcribe_audio_task
from controllers.DashboardController import DashboardController, MIME_TYPES
from repositories.VectorStoreRepository import VectorStoreRepository
from models.dto.DeleteRecordingRequestDTO import DeleteRecordingRequestDTO
from models.dto.FolderRequestDTO import CreateFolderRequestDTO, RenameFolderRequestDTO, DeleteFolderRequestDTO
from models.dto.GenerateTasksRequestDTO import GenerateTasksRequestDTO
from models.dto.MoveRecordingRequestDTO import MoveRecordingRequestDTO, BulkMoveRecordingsRequestDTO
from models.dto.PublishRequestDTO import PublishRequestDTO
from models.dto.SummarizeRequestDTO import SummarizeRequestDTO
from models.dto.TranscribeRequestDTO import TranscribeRequestDTO
from models.dto.UpdateRecordingRequestDTO import UpdateRecordingRequestDTO
from models.dto.UpdateSummaryRequestDTO import UpdateSummaryRequestDTO
from models.dto.UpdateTaskRequestDTO import UpdateTaskRequestDTO
from models.dto.UpdateTranscriptRequestDTO import UpdateTranscriptRequestDTO

router = APIRouter()


@router.get("/recordings")
def recordings_status(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_recordings_status()


@router.post("/upload")
async def upload_recording(
    file: UploadFile = File(...),
    label: str = Form(""),
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    file_data = await file.read()
    # The save + DB insert is blocking; offload it so it doesn't park the event
    # loop (keeps the frontend responsive and lets parallel uploads overlap).
    return await run_in_threadpool(
        dashboard_controller.upload_recording, file.filename, file_data, label
    )


@router.get("/audio/{name}")
async def get_audio(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    path, file_ext = dashboard_controller.get_audio_file_path(name)
    if not path:
        raise HTTPException(status_code=404, detail="Audio file not found")
    mime = MIME_TYPES.get(file_ext, "audio/mpeg")
    return FileResponse(path, media_type=mime, filename=f"{name}.{file_ext}")


@router.post("/transcribe/{name}")
def transcribe_recording(
    name: str,
    body: TranscribeRequestDTO = TranscribeRequestDTO(),
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    # Already transcribed → return synchronously, no need to queue.
    cached = dashboard_controller.get_cached_transcript(name)
    if cached:
        return {"ok": True, "transcript": cached, "cached": True}

    bare = dashboard_controller.bare_name(name)
    key = task_locks.transcribe_lock_key(bare)
    task_id = str(uuid.uuid4())

    # Claim the lock before queueing so duplicate requests across workers don't re-transcribe.
    if task_locks.acquire(key, task_id):
        dashboard_controller.set_transcription_status(bare, "queued")
        transcribe_audio_task.apply_async(args=[bare, body.engine], task_id=task_id)
        return {
            "ok": True,
            "task_id": task_id,
            "status": "queued",
            "message": f"Transcription task queued: {task_id}",
        }

    # Another request is already transcribing this file — poll its task instead.
    return {
        "ok": True,
        "task_id": task_locks.current_holder(key),
        "status": "already_running",
        "message": "Transcription already in progress",
    }


@router.get("/transcript/{name}")
def get_transcript(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_transcript(name)


@router.patch("/transcript/{name}")
def update_transcript(
    name: str,
    body: UpdateTranscriptRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_transcript(name, body.transcript)


@router.delete("/transcript/{name}")
def delete_transcript(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
    vector_store: VectorStoreRepository = Depends(depends.get_vector_store_repository),
):
    # vector_store is resolved only on this route, so ChromaDB isn't loaded on every request.
    return dashboard_controller.delete_transcript(name, vector_store=vector_store)


@router.get("/prompts")
def list_system_prompts(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.list_system_prompts()


@router.post("/summarize/{name}")
def summarize_recording(
    name: str,
    body: SummarizeRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    bare = dashboard_controller.bare_name(name)
    key = task_locks.summarize_lock_key(bare, body.prompt_id)
    task_id = str(uuid.uuid4())

    if task_locks.acquire(key, task_id):
        summarize_audio_task.apply_async(args=[bare, body.prompt_id], task_id=task_id)
        return {
            "ok": True,
            "task_id": task_id,
            "status": "queued",
            "message": f"Summarization task queued: {task_id}",
        }

    return {
        "ok": True,
        "task_id": task_locks.current_holder(key),
        "status": "already_running",
        "message": "Summarization already in progress",
    }


@router.get("/summaries/{name}")
def get_summaries(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_summaries(name)


# Legacy alias: keep old route name but return all summaries.
@router.get("/summary/{name}")
def get_summary_legacy(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_summaries(name)


@router.get("/share/destinations")
def share_destinations(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_publish_destinations()


@router.post("/share/summary/{summary_id}")
def publish_summary(
    summary_id: int,
    body: PublishRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.publish_summary(summary_id, body.destination)


# Legacy alias: publish latest summary for this recording.
@router.post("/share/{name}")
def publish_recording(
    name: str,
    body: PublishRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.publish_recording(name, body.destination)


@router.patch("/summary/{summary_id}")
def update_summary(
    summary_id: int,
    body: UpdateSummaryRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_summary(summary_id, body.title, body.tags, body.summary)


@router.patch("/recording/{name}")
def update_recording(
    name: str,
    body: UpdateRecordingRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_recording_datetime(name, body.recorded_at)


@router.delete("/recording/{name}")
def delete_recording(
    name: str,
    body: DeleteRecordingRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.delete_recording(
        name,
        body.delete_local,
        body.delete_db,
    )


# ─── Tasks ───────────────────────────────────────────────────────


@router.post("/tasks/generate")
def generate_tasks(
    body: GenerateTasksRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    key = task_locks.generate_lock_key(body.summary_id)
    task_id = str(uuid.uuid4())

    if task_locks.acquire(key, task_id):
        generate_tasks_task.apply_async(args=[body.summary_id], task_id=task_id)
        return {
            "ok": True,
            "task_id": task_id,
            "status": "queued",
            "message": f"Task generation queued: {task_id}",
        }

    return {
        "ok": True,
        "task_id": task_locks.current_holder(key),
        "status": "already_running",
        "message": "Task generation already in progress",
    }


# ─── Async task status ───────────────────────────────────────────
# NOTE: these /tasks/status/... routes must be declared BEFORE /tasks/{summary_id}
# so the {summary_id} path param does not swallow "status".


@router.get("/tasks/status/{task_id}")
def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    if state == "PROGRESS":
        return {"task_id": task_id, "status": "PROGRESS", "meta": result.info}
    if state == "SUCCESS":
        return {"task_id": task_id, "status": "SUCCESS", "result": result.result}
    if state == "FAILURE":
        return {"task_id": task_id, "status": "FAILURE", "error": str(result.info)}
    # PENDING (unknown/queued) or any custom state
    return {"task_id": task_id, "status": state}


@router.delete("/tasks/status/{task_id}")
def cancel_task(task_id: str):
    celery_app.control.revoke(task_id, terminate=True)
    return {"ok": True, "message": f"Task {task_id} revoked"}


@router.get("/tasks/active")
def active_tasks():
    """In-flight tasks (from the Redis locks) so the UI can resume polling after a page refresh.

    Declared before /tasks/{summary_id} so the path param doesn't swallow "active".
    """
    tasks = []
    for entry in task_locks.list_active():
        parts = entry["key"].split(":")  # ["lock", <type>, ...]
        if len(parts) < 3:
            continue
        ttype = parts[1]
        item = {"type": ttype, "task_id": entry["task_id"]}
        if ttype == "transcribe":
            item["name"] = ":".join(parts[2:])
        elif ttype == "summarize":
            item["name"] = parts[2]
            item["prompt_id"] = ":".join(parts[3:]) if len(parts) > 3 else None
        elif ttype == "generate":
            item["summary_id"] = parts[2]
        tasks.append(item)
    return {"tasks": tasks}


@router.get("/tasks/{summary_id}")
def get_tasks(
    summary_id: int,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_tasks(summary_id)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    body: UpdateTaskRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_task(
        task_id, title=body.title, description=body.description, status=body.status
    )


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.delete_task(task_id)


# ─── Folders ─────────────────────────────────────────────────────


@router.get("/folders")
def get_folders(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_folders()


@router.post("/folders")
def create_folder(
    body: CreateFolderRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.create_folder(body.path)


@router.patch("/folders/rename")
def rename_folder(
    body: RenameFolderRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.rename_folder(body.old_path, body.new_path)


@router.delete("/folders")
def delete_folder(
    body: DeleteFolderRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.delete_folder(body.path, body.move_to)


@router.patch("/recording/{name}/move")
def move_recording(
    name: str,
    body: MoveRecordingRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.move_recording(name, body.folder)


@router.patch("/recordings/move")
def bulk_move_recordings(
    body: BulkMoveRecordingsRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.bulk_move_recordings(body.names, body.folder)
