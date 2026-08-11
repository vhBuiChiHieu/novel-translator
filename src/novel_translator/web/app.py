from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from .errors import WebError, map_exception
from .routes import (
    chapters,
    context,
    diagnostics,
    events,
    exports,
    health,
    imports,
    operations,
    projects,
    session,
    settings,
    translations,
)
from .routes import runtime as runtime_routes
from .runtime import WebRuntime

APP_VERSION = "0.1.0"
STATIC_ROOT = Path(__file__).with_name("static")


def create_app(runtime: WebRuntime | None = None) -> FastAPI:
    local_runtime = runtime or WebRuntime()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        local_runtime.close()

    app = FastAPI(
        title="Novel Translator Local Web API",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.runtime = local_runtime

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(WebError)
    async def web_error_handler(_: Request, error: WebError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content=error.as_response())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
        details = {"fields": [{"loc": list(item["loc"]), "msg": item["msg"]} for item in error.errors()]}
        response = WebError(422, "VALIDATION_ERROR", "The request payload is invalid.", details)
        return JSONResponse(status_code=422, content=response.as_response())

    @app.exception_handler(Exception)
    async def exception_handler(_: Request, error: Exception) -> JSONResponse:
        mapped = map_exception(error)
        return JSONResponse(status_code=mapped.status_code, content=mapped.as_response())

    app.include_router(health.router)
    app.include_router(session.router)
    app.include_router(projects.router)
    app.include_router(projects.dashboard_router)
    app.include_router(runtime_routes.router)
    app.include_router(settings.router)
    app.include_router(imports.router)
    app.include_router(chapters.router)
    app.include_router(translations.router)
    app.include_router(operations.router)
    app.include_router(events.router)
    app.include_router(context.router)
    app.include_router(exports.router)
    app.include_router(diagnostics.router)

    index = STATIC_ROOT / "index.html"

    @app.get("/", include_in_schema=False)
    async def index_page() -> Response:
        if index.is_file():
            return FileResponse(index)
        return Response("Novel Translator local web app", media_type="text/plain")

    @app.get("/{asset_path:path}", include_in_schema=False)
    async def spa_fallback(asset_path: str) -> Response:
        requested = STATIC_ROOT / asset_path
        if requested.is_file() and STATIC_ROOT in requested.resolve().parents:
            return FileResponse(requested)
        if index.is_file():
            return FileResponse(index)
        return Response("Novel Translator local web app", media_type="text/plain")

    return app
