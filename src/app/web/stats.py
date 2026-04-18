from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import depends

router = APIRouter()


@router.get("/stats", response_class=HTMLResponse)
def stats_home(request: Request):
    template_path = depends.get_template_path()
    templates = Jinja2Templates(directory=template_path)
    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={"active_page": "stats", "auth_enabled": depends.is_auth_enabled()},
    )
