from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from novel_translator.web.dependencies import require_session
from novel_translator.web.errors import WebError
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import ApiKeyRequest, ApiKeyStatus, SettingsPatch
from novel_translator.web.serializers import safe_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
def get_settings(runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    return safe_settings(runtime.current_facade().session.settings)


@router.patch("")
async def update_settings(request: SettingsPatch, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    updates = request.model_dump(exclude_unset=True)
    model = updates.get("model")
    if isinstance(model, dict) and "api_key" in model:
        raise WebError(422, "CREDENTIAL_WRITE_ONLY", "Use the write-only model API key endpoint.")
    operation = runtime.submit(
        "settings_update",
        lambda _operation: safe_settings(runtime.current_facade().update_settings(updates)),
    )
    await runtime.wait(operation)
    result = runtime.operation_result_or_raise(operation)
    return result if isinstance(result, dict) else {}


@router.put("/model-api-key", status_code=status.HTTP_204_NO_CONTENT)
async def set_model_api_key(request: ApiKeyRequest, runtime: WebRuntime = Depends(require_session)) -> Response:
    def work(_operation) -> dict[str, object]:
        runtime.current_facade().set_api_key(request.api_key)
        return {}

    operation = runtime.submit(
        "settings_update",
        work,
    )
    await runtime.wait(operation)
    runtime.operation_result_or_raise(operation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/model-api-key/status", response_model=ApiKeyStatus)
def model_api_key_status(runtime: WebRuntime = Depends(require_session)) -> ApiKeyStatus:
    settings = runtime.current_facade().session.settings
    return ApiKeyStatus(configured=settings.model.api_key is not None)
