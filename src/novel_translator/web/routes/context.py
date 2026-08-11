from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import ConflictResolveRequest, ContextRequest

router = APIRouter(prefix="/api/v1/context", tags=["context"])


@router.get("")
def list_context(
    context_type: str | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
    runtime: WebRuntime = Depends(require_session),
) -> list[dict[str, object]]:
    return [
        item.model_dump(mode="json")
        for item in runtime.current_facade().list_context(context_type=context_type, status=status_filter)
    ]


@router.post("")
async def upsert_context(request: ContextRequest, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    operation = runtime.submit(
        "context_mutation",
        lambda _operation: {
            "id": runtime.current_facade().upsert_context(
                request.context_type,
                request.source,
                request.translation,
                request.description,
                request.status,
            )
        },
    )
    await runtime.wait(operation)
    return runtime.operation_result_or_raise(operation)  # type: ignore[return-value]


@router.delete("/{context_type}/{source:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context(context_type: str, source: str, runtime: WebRuntime = Depends(require_session)) -> Response:
    def work(_operation) -> dict[str, object]:
        runtime.current_facade().delete_context(context_type, source)
        return {}

    operation = runtime.submit(
        "context_mutation",
        work,
    )
    await runtime.wait(operation)
    runtime.operation_result_or_raise(operation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conflicts")
def list_conflicts(runtime: WebRuntime = Depends(require_session)) -> list[dict[str, object]]:
    return [conflict.model_dump(mode="json") for conflict in runtime.current_facade().list_conflicts()]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int, request: ConflictResolveRequest, runtime: WebRuntime = Depends(require_session)
) -> dict[str, object]:
    def work(_operation) -> dict[str, object]:
        runtime.current_facade().resolve_conflict(conflict_id, request.action, request.value)
        return {}

    operation = runtime.submit(
        "context_mutation",
        work,
    )
    await runtime.wait(operation)
    return runtime.operation_result_or_raise(operation)  # type: ignore[return-value]
