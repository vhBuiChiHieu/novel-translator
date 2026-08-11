from __future__ import annotations

from fastapi import APIRouter, Depends

from novel_translator.web.dependencies import get_runtime
from novel_translator.web.runtime import WebRuntime

router = APIRouter(prefix="/api/v1", tags=["health"])
APP_VERSION = "0.1.0"


@router.get("/health")
def health(runtime: WebRuntime = Depends(get_runtime)) -> dict[str, object]:
    return {
        "version": APP_VERSION,
        "status": "shutting_down" if runtime.closed else "ok",
        "loopback_only": True,
        "project_open": runtime.project_path is not None,
    }
