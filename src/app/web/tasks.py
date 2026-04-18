from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import depends

router = APIRouter()


@router.get("/tasks", response_class=HTMLResponse)
def tasks_home(request: Request):
    template_path = depends.get_template_path()
    templates = Jinja2Templates(directory=template_path)
    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={"active_page": "tasks", "auth_enabled": depends.is_auth_enabled()},
    )
