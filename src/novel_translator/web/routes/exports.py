from __future__ import annotations

from fastapi import APIRouter, Depends, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import ExportRequest, OperationResponse

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.post("", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
def export_project(request: ExportRequest, runtime: WebRuntime = Depends(require_session)) -> OperationResponse:
    def work(_operation):
        facade = runtime.current_facade()
        output = facade.export_context() if request.kind == "context" else facade.export_novel()
        return {"kind": request.kind, "output_path": str(output)}

    operation = runtime.submit("export", work)
    return OperationResponse(operation_id=operation.operation_id, status="queued")
