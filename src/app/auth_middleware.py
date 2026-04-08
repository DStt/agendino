import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from services.AuthService import AuthService

logger = logging.getLogger(__name__)

# Paths that never require authentication
PUBLIC_PATHS = frozenset({"/login", "/api/auth/login", "/api/auth/logout"})
PUBLIC_PREFIXES = ("/static/",)

SESSION_COOKIE = "agendino_session"


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_service: AuthService):
        super().__init__(app)
        self.auth_service = auth_service

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Block banned IPs immediately
        client_ip = request.client.host if request.client else "unknown"
        if self.auth_service.is_ip_banned(client_ip):
            logger.warning("Blocked request from banned IP %s", client_ip)
            return JSONResponse({"detail": "Forbidden"}, status_code=403)

        # Allow public paths through
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Check session cookie
        session_token = request.cookies.get(SESSION_COOKIE)
        if session_token and self.auth_service.validate_session(session_token):
            return await call_next(request)

        # Not authenticated
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        # Redirect browser requests to login
        return RedirectResponse(url="/login", status_code=302)
