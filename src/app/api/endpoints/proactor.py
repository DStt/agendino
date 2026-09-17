from fastapi import APIRouter, Depends

from app import depends
from controllers.ProactorController import ProactorController
from models.dto.ProactorAnalyzeRequestDTO import ProactorAnalyzeRequestDTO

router = APIRouter()


@router.get("/analyze")
def proactor_analyze(
    start: str,
    end: str,
    proactor_controller: ProactorController = Depends(depends.get_proactor_controller),
):
    return proactor_controller.analyze_date_range(start, end)


@router.post("/analyze")
def proactor_analyze_post(
    body: ProactorAnalyzeRequestDTO,
    proactor_controller: ProactorController = Depends(depends.get_proactor_controller),
):
    return proactor_controller.analyze_date_range(body.start_date, body.end_date)
