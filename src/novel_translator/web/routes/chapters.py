from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])


@router.get("")
def list_chapters(
    status: str | None = Query(default=None), runtime: WebRuntime = Depends(require_session)
) -> list[dict[str, object]]:
    return [chapter.model_dump(mode="json") for chapter in runtime.current_facade().list_chapters(status)]


@router.get("/{chapter_number}")
def get_chapter(chapter_number: int, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    return runtime.current_facade().get_chapter(chapter_number).model_dump(mode="json")
