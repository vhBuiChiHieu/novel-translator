from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.errors import WebError
from novel_translator.web.runtime import WebRuntime, iso_now
from novel_translator.web.schemas import ImportPreviewRequest, ImportRequest, OperationResponse

router = APIRouter(prefix="/api/v1", tags=["imports"])


def absolute_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise WebError(422, "PATH_INVALID", "Directory path must be absolute.")
    return path


@router.post("/import/preview")
def preview_import(request: ImportPreviewRequest, runtime: WebRuntime = Depends(require_session)) -> list[dict[str, object]]:
    previews = runtime.current_facade().preview_import(absolute_directory(request.source_directory))
    return [preview.model_dump(mode="json") for preview in previews]


@router.post("/imports", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
def import_chapters(request: ImportRequest, runtime: WebRuntime = Depends(require_session)) -> OperationResponse:
    source_directory = absolute_directory(request.source_directory)

    def work(operation):
        count = runtime.current_facade().import_chapters(source_directory)
        runtime.broker.publish(
            "import_completed",
            {"operation_id": operation.operation_id, "event": "import_completed", "imported": count, "at": iso_now()},
        )
        return {"imported": count}

    operation = runtime.submit("import", work)
    return OperationResponse(operation_id=operation.operation_id, status="queued")
