from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, File, Form
from fastapi.responses import FileResponse

from app import depends
from controllers.DashboardController import DashboardController, MIME_TYPES
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

# A recording name is a bare filename: no separators, no traversal, no NUL.
RecordingName = Annotated[
    str,
    Path(min_length=1, max_length=255, pattern=r"^[^/\\\x00]+$"),
]


@router.get("/recordings")
def recordings_status(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_recordings_status()


@router.post("/upload")
def upload_recording(
    file: UploadFile = File(...),
    label: str = Form(""),
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    file_data = file.file.read()
    return dashboard_controller.upload_recording(file.filename, file_data, label)


@router.get("/audio/{name}")
def get_audio(
    name: RecordingName,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    path, file_ext = dashboard_controller.get_audio_file_path(name)
    if not path:
        raise HTTPException(status_code=404, detail="Audio file not found")
    mime = MIME_TYPES.get(file_ext, "audio/mpeg")
    return FileResponse(path, media_type=mime, filename=f"{name}.{file_ext}")


@router.post("/transcribe/{name}")
def transcribe_recording(
    name: RecordingName,
    body: TranscribeRequestDTO = TranscribeRequestDTO(),
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.transcribe_recording(name, engine=body.engine)


@router.get("/transcript/{name}")
def get_transcript(
    name: RecordingName,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_transcript(name)


@router.patch("/transcript/{name}")
def update_transcript(
    name: RecordingName,
    body: UpdateTranscriptRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_transcript(name, body.transcript)


@router.get("/prompts")
def list_system_prompts(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.list_system_prompts()


@router.get("/ai-providers")
def get_ai_providers(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_ai_providers()


@router.post("/summarize/{name}")
def summarize_recording(
    name: RecordingName,
    body: SummarizeRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.summarize_recording(name, body.prompt_id, provider=body.provider)


@router.get("/summaries/{name}")
def get_summaries(
    name: RecordingName,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_summaries(name)


# Legacy alias: keep old route name but return all summaries.
@router.get("/summary/{name}")
def get_summary_legacy(
    name: RecordingName,
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
    name: RecordingName,
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
    name: RecordingName,
    body: UpdateRecordingRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_recording_datetime(name, body.recorded_at)


@router.delete("/recording/{name}")
def delete_recording(
    name: RecordingName,
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
    return dashboard_controller.generate_tasks(body.summary_id, provider=body.provider)


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
    name: RecordingName,
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
