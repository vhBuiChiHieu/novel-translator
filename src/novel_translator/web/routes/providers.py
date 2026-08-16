from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from novel_translator.application.services.global_provider_service import GlobalProviderService
from novel_translator.domain.model.catalog import model_catalog
from novel_translator.web.dependencies import require_session
from novel_translator.web.runtime import WebRuntime
from novel_translator.web.schemas import (
    ProviderCredentialRequest,
    ProviderProfilePatch,
    ProviderProfileRequest,
)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


def service() -> GlobalProviderService:
    return GlobalProviderService()


@router.get("")
def list_providers(_: WebRuntime = Depends(require_session)) -> dict[str, object]:
    current = service()
    settings = current.settings()
    return {
        "config_version": settings.config_version,
        "active_profile": settings.active_profile,
        "profiles": list(current.list_profiles().values()),
        "model_options": model_catalog(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_provider(request: ProviderProfileRequest, _: WebRuntime = Depends(require_session)) -> dict[str, object]:
    if not request.profile_id:
        raise ValueError("profile_id is required")
    data = request.model_dump(exclude={"profile_id"})
    return service().create(request.profile_id, data)


@router.patch("/{profile_id}")
def update_provider(profile_id: str, request: ProviderProfilePatch, _: WebRuntime = Depends(require_session)) -> dict[str, object]:
    return service().update(profile_id, request.model_dump(exclude_unset=True))


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(profile_id: str, _: WebRuntime = Depends(require_session)) -> Response:
    service().delete(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{profile_id}/activate")
def activate_provider(profile_id: str, _: WebRuntime = Depends(require_session)) -> dict[str, object]:
    return service().activate(profile_id)


@router.put("/{profile_id}/credential", status_code=status.HTTP_204_NO_CONTENT)
def set_provider_credential(
    profile_id: str, request: ProviderCredentialRequest, _: WebRuntime = Depends(require_session)
) -> Response:
    service().set_credential(profile_id, request.api_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{profile_id}/credential/status")
def provider_credential_status(profile_id: str, _: WebRuntime = Depends(require_session)) -> dict[str, bool]:
    return service().credential_status(profile_id)


@router.post("/{profile_id}/test")
async def test_provider(profile_id: str, runtime: WebRuntime = Depends(require_session)) -> dict[str, object]:
    operation = runtime.submit(
        "provider_test",
        lambda _operation: service().test_connection(profile_id),
        allow_without_project=True,
    )
    await runtime.wait(operation)
    result = runtime.operation_result_or_raise(operation)
    return result if isinstance(result, dict) else {}
