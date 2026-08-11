from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import OperationResponse, TranslationRangeRequest, TranslationRequest
from novel_translator.web.serializers import redact_sensitive

router = APIRouter(prefix="/api/v1", tags=["translations"])


@router.post("/translations", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
def translate(request: TranslationRequest, runtime: WebRuntime = Depends(require_session)) -> OperationResponse:
    def work(operation):
        facade = runtime.current_facade()
        job = facade.translate(
            request.chapter_number,
            resume=request.resume,
            force=request.force,
            on_progress=lambda progress: runtime.publish_progress(operation, progress),
            should_cancel=operation.is_cancel_requested,
        )
        return {"jobs": [job.model_dump(mode="json")]}

    operation = runtime.submit("translate_chapter", work, [request.chapter_number])
    return OperationResponse(
        operation_id=operation.operation_id,
        status="queued",
        chapter_numbers=operation.chapter_numbers,
    )


@router.post("/translations/range", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
def translate_range(request: TranslationRangeRequest, runtime: WebRuntime = Depends(require_session)) -> OperationResponse:
    if request.last < request.first:
        from novel_translator.web.errors import WebError

        raise WebError(422, "RANGE_INVALID", "The last chapter must be greater than or equal to the first chapter.")
    chapter_numbers = list(range(request.first, request.last + 1))

    def work(operation):
        facade = runtime.current_facade()
        jobs = facade.translate_range(
            request.first,
            request.last,
            resume=request.resume,
            force=request.force,
            on_progress=lambda progress: runtime.publish_progress(operation, progress),
            should_cancel=operation.is_cancel_requested,
        )
        return {"jobs": [job.model_dump(mode="json") for job in jobs]}

    operation = runtime.submit("translate_range", work, chapter_numbers)
    return OperationResponse(
        operation_id=operation.operation_id,
        status="queued",
        chapter_numbers=chapter_numbers,
    )


@router.get("/translation-jobs")
def list_jobs(
    chapter_number: int | None = Query(default=None, ge=1), runtime: WebRuntime = Depends(require_session)
) -> list[dict[str, object]]:
    return [job.model_dump(mode="json") for job in runtime.current_facade().list_jobs(chapter_number)]


@router.get("/translation-chunks/{chunk_id}")
def get_chunk_detail(chunk_id: int, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    facade = runtime.current_facade()
    chunk = facade.get_chunk_detail(chunk_id)
    api_key = facade.session.settings.model.api_key.get_secret_value() if facade.session.settings.model.api_key else ""
    return redact_sensitive(chunk.model_dump(mode="json"), (api_key,))
