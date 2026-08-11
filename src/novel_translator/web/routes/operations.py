from __future__ import annotations

from fastapi import APIRouter, Depends, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import CancelResponse, OperationView

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


@router.get("/{operation_id}", response_model=OperationView)
def get_operation(operation_id: str, runtime: WebRuntime = Depends(require_session)) -> OperationView:
    return OperationView.model_validate(runtime.get_operation(operation_id).as_dict())


@router.post("/{operation_id}/cancel", response_model=CancelResponse, status_code=status.HTTP_202_ACCEPTED)
def cancel_operation(operation_id: str, runtime: WebRuntime = Depends(require_session)) -> CancelResponse:
    operation = runtime.cancel(operation_id)
    return CancelResponse(
        operation_id=operation.operation_id,
        status=operation.status,
        message="Stopping after current chunk.",
    )
