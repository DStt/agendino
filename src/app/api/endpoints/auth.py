from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import depends
from app.auth_middleware import SESSION_COOKIE
from services.AuthService import AuthService

router = APIRouter()

SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, auth_service: AuthService = Depends(depends.get_auth_service)):
    if not auth_service.authenticate(body.username, body.password):
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)

    token = auth_service.create_session()
    response = JSONResponse({"authorization": token, "status": "ok"})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request, auth_service: AuthService = Depends(depends.get_auth_service)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        auth_service.destroy_session(token)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
