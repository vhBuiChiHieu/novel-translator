from __future__ import annotations

from fastapi import APIRouter, Depends, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import CurrentProjectResponse, OperationResponse, ProjectPathRequest, ResetRequest
from novel_translator.web.serializers import safe_dashboard

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
dashboard_router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/current", response_model=CurrentProjectResponse)
def current_project(runtime: WebRuntime = Depends(require_session)) -> CurrentProjectResponse:
    path = runtime.project_path
    if path is None:
        return CurrentProjectResponse(open=False, validation_errors=runtime.startup_error)
    facade = runtime.current_facade()
    return CurrentProjectResponse(open=True, project=facade.session.novel, path=str(path))


@router.post("/open", response_model=CurrentProjectResponse)
def open_project(request: ProjectPathRequest, runtime: WebRuntime = Depends(require_session)) -> CurrentProjectResponse:
    from pathlib import Path

    path = Path(request.path)
    if not path.is_absolute():
        from novel_translator.web.errors import WebError

        raise WebError(422, "PROJECT_PATH_INVALID", "Project path must be absolute.")
    runtime.open_project(path)
    facade = runtime.current_facade()
    return CurrentProjectResponse(open=True, project=facade.session.novel, path=str(path.resolve()))


@router.post("/reset", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
def reset_project(_: ResetRequest, runtime: WebRuntime = Depends(require_session)) -> OperationResponse:
    operation = runtime.submit(
        "reset",
        lambda _operation: {"project": runtime.current_facade().reset_project().novel.model_dump(mode="json")},
    )
    return OperationResponse(operation_id=operation.operation_id, status="queued")


@router.get("/recent")
def recent_projects(runtime: WebRuntime = Depends(require_session)) -> dict[str, list[str]]:
    return {"projects": runtime.recent_projects}


@dashboard_router.get("/dashboard")
def dashboard(runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    return safe_dashboard(runtime.current_facade().get_dashboard())
