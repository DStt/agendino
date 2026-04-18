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
    engines: list[str]


class SummarizationCompareRequest(BaseModel):
    recording_name: str
    prompt_ids: list[str]


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
    bare_name = body.recording_name
    db_rec = db.get_recording_by_name(bare_name)
    if not db_rec:
        return {"ok": False, "error": f"Recording '{bare_name}' not found"}

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
        return {"ok": False, "error": "No transcript found - transcribe first"}

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
