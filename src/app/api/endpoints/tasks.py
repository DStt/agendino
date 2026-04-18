from fastapi import APIRouter, Depends

from app import depends
from repositories.SqliteDBRepository import SqliteDBRepository

router = APIRouter()


@router.get("/all")
async def get_all_tasks(
    status: str | None = None,
    db: SqliteDBRepository = Depends(depends.get_sqlite_db_repository),
):
    tasks = db.get_all_tasks_grouped()
    if status and status != "all":
        tasks = [t for t in tasks if t["status"] == status]
    return {"ok": True, "tasks": tasks}
