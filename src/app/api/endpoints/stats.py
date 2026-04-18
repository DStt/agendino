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
