from __future__ import annotations

from fastapi import APIRouter, Depends, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.errors import WebError
from novel_translator.web.native_picker import NativePickerUnavailable, choose_directory
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import (
    CreateProjectRequest,
    CurrentProjectResponse,
    DirectoryPickerRequest,
    OperationResponse,
    ProjectPathRequest,
    ResetRequest,
)
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
        raise WebError(422, "PROJECT_PATH_INVALID", "Project path must be absolute.")
    runtime.open_project(path)
    facade = runtime.current_facade()
    return CurrentProjectResponse(open=True, project=facade.session.novel, path=str(path.resolve()))


@router.post("/pick")
def pick_directory(request: DirectoryPickerRequest, _: WebRuntime = Depends(require_session)) -> dict[str, str | None]:
    titles = {
        "project": "Chọn thư mục project",
        "parent": "Chọn thư mục cha để tạo project",
        "source": "Chọn thư mục chứa chapter",
    }
    try:
        selected = choose_directory(title=titles[request.purpose])
    except NativePickerUnavailable as error:
        raise WebError(503, "NATIVE_PICKER_UNAVAILABLE", str(error)) from error
    return {"path": str(selected) if selected is not None else None}


@router.post("/create", response_model=CurrentProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(request: CreateProjectRequest, runtime: WebRuntime = Depends(require_session)) -> CurrentProjectResponse:
    from pathlib import Path

    path = runtime.create_project(Path(request.parent_path), request.name)
    facade = runtime.current_facade()
    return CurrentProjectResponse(open=True, project=facade.session.novel, path=str(path))


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
