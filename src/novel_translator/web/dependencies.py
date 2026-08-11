from __future__ import annotations

from fastapi import Depends, Request

from .runtime import WebRuntime


def get_runtime(request: Request) -> WebRuntime:
    return request.app.state.runtime


def require_session(request: Request, runtime: WebRuntime = Depends(get_runtime)) -> WebRuntime:
    runtime.require_session(request)
    return runtime
