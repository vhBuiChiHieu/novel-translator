from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


@router.post("/quit", status_code=status.HTTP_202_ACCEPTED)
def quit_server(request: Request, runtime: WebRuntime = Depends(require_session)) -> dict[str, str]:
    server = getattr(request.app.state, "server", None)
    if server is not None:
        server.should_exit = True
    return {"status": "shutting_down"}
