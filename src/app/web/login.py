import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.depends import is_auth_enabled

router = APIRouter()

_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../templates/login/login.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    if not is_auth_enabled():
        return RedirectResponse("/")

    with open(_TEMPLATE_PATH, "r") as f:
        return HTMLResponse(content=f.read())
