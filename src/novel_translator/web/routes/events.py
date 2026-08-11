from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import EventRecord, WebRuntime

router = APIRouter(prefix="/api/v1", tags=["events"])


def format_sse(record: EventRecord) -> str:
    if record.id == 0:
        return ": keep-alive\n\n"
    return f"id: {record.id}\nevent: {record.event}\ndata: {json.dumps(record.data, ensure_ascii=False)}\n\n"


@router.get("/events")
async def events(
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    runtime: WebRuntime = Depends(require_session),
) -> StreamingResponse:
    async def stream():
        iterator = runtime.events_for(last_event_id)
        while True:
            record = await asyncio.to_thread(next, iterator)
            yield format_sse(record)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
