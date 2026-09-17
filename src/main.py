import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth_middleware import AuthMiddleware
from app.depends import get_auth_service, is_auth_enabled, validate_config
from app.router import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger("agendino")

# Log the effective configuration (non-fatal) before serving requests.
validate_config()

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="AgenDino")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

if is_auth_enabled():
    app.add_middleware(AuthMiddleware, auth_service=get_auth_service())


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness probe; public so monitoring works when auth is enabled."""
    return {"ok": True, "status": "healthy"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return the app's standard error envelope for HTTP errors."""
    return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"ok": False, "error": "Internal server error"}, status_code=500)


app.include_router(router)
