from fastapi import APIRouter

from .endpoints import auth
from .endpoints import calendar
from .endpoints import dashboard
from .endpoints import knowledge
from .endpoints import proactor
from .endpoints import stats

router = APIRouter()

router.include_router(auth.router, prefix="/auth")
router.include_router(dashboard.router, prefix="/dashboard")
router.include_router(calendar.router, prefix="/calendar")
router.include_router(proactor.router, prefix="/proactor")
router.include_router(knowledge.router, prefix="/knowledge")
router.include_router(stats.router, prefix="/stats")
