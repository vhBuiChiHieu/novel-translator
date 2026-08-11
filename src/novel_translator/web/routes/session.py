from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from novel_translator.web.dependencies import get_runtime
from novel_translator.web.runtime import SESSION_COOKIE, WebRuntime
from novel_translator.web.schemas import BootstrapResponse

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    response: Response,
    request: Request,
    x_local_app_token: str | None = Header(default=None),
    runtime: WebRuntime = Depends(get_runtime),
) -> BootstrapResponse:
    runtime.validate_loopback_request(request)
    runtime.bootstrap(x_local_app_token)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=runtime.session_token,
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return BootstrapResponse()
