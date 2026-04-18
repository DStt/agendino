from fastapi import APIRouter

from app.api.api import router as api_router
from app.web.compare import router as compare_router
from app.web.dashboard import router as web_router
from app.web.knowledge import router as knowledge_router
from app.web.login import router as login_router
from app.web.stats import router as stats_router
from app.web.tasks import router as tasks_router

router = APIRouter()

router.include_router(api_router, prefix="/api")
router.include_router(login_router, prefix="")
router.include_router(web_router, prefix="")
router.include_router(knowledge_router, prefix="")
router.include_router(stats_router, prefix="")
router.include_router(compare_router, prefix="")
router.include_router(tasks_router, prefix="")
