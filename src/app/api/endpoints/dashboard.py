from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app import depends
from controllers.DashboardController import DashboardController, MIME_TYPES
from models.dto.DeleteRecordingRequestDTO import DeleteRecordingRequestDTO
from models.dto.GenerateTasksRequestDTO import GenerateTasksRequestDTO
from models.dto.PublishRequestDTO import PublishRequestDTO
from models.dto.SummarizeRequestDTO import SummarizeRequestDTO
from models.dto.TranscribeRequestDTO import TranscribeRequestDTO
from models.dto.UpdateRecordingRequestDTO import UpdateRecordingRequestDTO
from models.dto.UpdateSummaryRequestDTO import UpdateSummaryRequestDTO
from models.dto.UpdateTaskRequestDTO import UpdateTaskRequestDTO
from models.dto.UpdateTranscriptRequestDTO import UpdateTranscriptRequestDTO

router = APIRouter()


@router.get("/recordings")
async def recordings_status(
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
    return dashboard_controller.upload_recording(file.filename, file_data, label)


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
async def transcribe_recording(
    name: str,
    body: TranscribeRequestDTO = TranscribeRequestDTO(),
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.transcribe_recording(name, engine=body.engine)


@router.get("/transcript/{name}")
async def get_transcript(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_transcript(name)


@router.patch("/transcript/{name}")
async def update_transcript(
    name: str,
    body: UpdateTranscriptRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_transcript(name, body.transcript)


@router.get("/prompts")
async def list_system_prompts(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.list_system_prompts()


@router.post("/summarize/{name}")
async def summarize_recording(
    name: str,
    body: SummarizeRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.summarize_recording(name, body.prompt_id)


@router.get("/summaries/{name}")
async def get_summaries(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_summaries(name)


# Legacy alias: keep old route name but return all summaries.
@router.get("/summary/{name}")
async def get_summary_legacy(
    name: str,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_summaries(name)


@router.get("/share/destinations")
async def share_destinations(
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_publish_destinations()


@router.post("/share/summary/{summary_id}")
async def publish_summary(
    summary_id: int,
    body: PublishRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.publish_summary(summary_id, body.destination)


# Legacy alias: publish latest summary for this recording.
@router.post("/share/{name}")
async def publish_recording(
    name: str,
    body: PublishRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.publish_recording(name, body.destination)


@router.patch("/summary/{summary_id}")
async def update_summary(
    summary_id: int,
    body: UpdateSummaryRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_summary(summary_id, body.title, body.tags, body.summary)


@router.patch("/recording/{name}")
async def update_recording(
    name: str,
    body: UpdateRecordingRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_recording_datetime(name, body.recorded_at)


@router.delete("/recording/{name}")
async def delete_recording(
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
async def generate_tasks(
    body: GenerateTasksRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.generate_tasks(body.summary_id)


@router.get("/tasks/{summary_id}")
async def get_tasks(
    summary_id: int,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.get_tasks(summary_id)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: UpdateTaskRequestDTO,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.update_task(
        task_id, title=body.title, description=body.description, status=body.status
    )


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    dashboard_controller: DashboardController = Depends(depends.get_dashboard_controller),
):
    return dashboard_controller.delete_task(task_id)
