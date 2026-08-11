from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.serializers import safe_model_call

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/model-calls")
def list_model_calls(
    chunk_id: int | None = Query(default=None, ge=1), runtime: WebRuntime = Depends(require_session)
) -> list[dict[str, object]]:
    facade = runtime.current_facade()
    return [safe_model_call(call, facade.session.settings) for call in facade.list_model_calls(chunk_id)]


@router.get("/database/tables")
def list_database_tables(runtime: WebRuntime = Depends(require_session)) -> dict[str, list[str]]:
    return {"tables": runtime.current_facade().list_database_tables()}


@router.get("/database/tables/{table_name}")
def get_database_table(table_name: str, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    table = runtime.current_facade().get_database_table(table_name)
    return table.model_dump(mode="json")
