import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../templates/login/login.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    with open(_TEMPLATE_PATH, "r") as f:
        return HTMLResponse(content=f.read())
