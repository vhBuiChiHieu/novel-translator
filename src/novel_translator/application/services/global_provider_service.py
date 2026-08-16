from __future__ import annotations

import re
from typing import Any

import httpx

from novel_translator.config import (
    GlobalProviderSettings,
    ModelSettings,
    ProviderProfile,
    ProviderType,
)
from novel_translator.infrastructure.config.credentials import ProviderCredentialStore
from novel_translator.infrastructure.config.store import GlobalSettingsStore


class GlobalProviderService:
    """Application use cases for global provider profiles and credentials."""

    PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

    def __init__(
        self,
        store: GlobalSettingsStore | None = None,
        credentials: ProviderCredentialStore | None = None,
    ) -> None:
        self.store = store or GlobalSettingsStore()
        self.credentials = credentials or ProviderCredentialStore()

    def settings(self) -> GlobalProviderSettings:
        return self.store.load()

    def list_profiles(self) -> dict[str, dict[str, Any]]:
        settings = self.settings()
        return {
            profile_id: self.profile_response(profile_id, profile, settings.active_profile == profile_id)
            for profile_id, profile in settings.profiles.items()
        }

    def profile_response(self, profile_id: str, profile: ProviderProfile, active: bool = False) -> dict[str, Any]:
        return {
            "id": profile_id,
            "provider": profile.provider.value,
            "base_url": profile.base_url,
            "model": profile.model,
            "request_timeout_seconds": profile.request_timeout_seconds,
            "max_retries": profile.max_retries,
            "options": profile.options.model_dump(mode="json", exclude_none=True),
            "provider_options": profile.provider_options,
            "credential_ref": profile.credential_ref,
            "credential_configured": self.credentials.status(profile_id, profile),
            "active": active,
        }

    def create(self, profile_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._validate_profile_id(profile_id)
        settings = self.settings() if self.store.exists() else GlobalProviderSettings(config_version=2, active_profile="", profiles={})
        if profile_id in settings.profiles:
            raise ValueError(f"Provider profile already exists: {profile_id}")
        profile = self._profile_from_data(data)
        profile = profile.model_copy(update={"credential_ref": profile.credential_ref or profile_id})
        settings.profiles[profile_id] = profile
        if not settings.active_profile or len(settings.profiles) == 1:
            settings.active_profile = profile_id
        self.store.save(settings)
        return self.profile_response(profile_id, profile, settings.active_profile == profile_id)

    def update(self, profile_id: str, data: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings()
        current = self._get(settings, profile_id)
        merged = current.model_dump(exclude={"api_key"}, mode="python")
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        merged["provider"] = str(merged["provider"]).lower()
        updated = ProviderProfile.model_validate(merged)
        settings.profiles[profile_id] = updated
        self.store.save(settings)
        return self.profile_response(profile_id, updated, settings.active_profile == profile_id)

    def delete(self, profile_id: str) -> None:
        settings = self.settings()
        self._get(settings, profile_id)
        if len(settings.profiles) == 1:
            raise ValueError("At least one provider profile must remain")
        del settings.profiles[profile_id]
        if settings.active_profile == profile_id:
            settings.active_profile = next(iter(settings.profiles))
        self.store.save(settings)
        self.credentials.delete(profile_id)

    def activate(self, profile_id: str) -> dict[str, Any]:
        settings = self.settings()
        profile = self._get(settings, profile_id)
        settings.active_profile = profile_id
        self.store.save(settings)
        return self.profile_response(profile_id, profile, True)

    def set_credential(self, profile_id: str, value: str) -> None:
        settings = self.settings()
        profile = self._get(settings, profile_id)
        if profile.provider == ProviderType.OLLAMA:
            raise ValueError("Ollama does not use an API key")
        self.credentials.set(profile_id, value)

    def credential_status(self, profile_id: str) -> dict[str, bool]:
        settings = self.settings()
        profile = self._get(settings, profile_id)
        return {"configured": self.credentials.status(profile_id, profile)}

    def duplicate(self, source_id: str, target_id: str) -> dict[str, Any]:
        settings = self.settings()
        source = self._get(settings, source_id)
        return self.create(target_id, source.model_dump(exclude={"api_key"}, mode="python"))

    def test_connection(self, profile_id: str) -> dict[str, Any]:
        settings = self.settings()
        profile = self._get(settings, profile_id)
        credential = self.credentials.get(profile_id, profile)
        headers = {"x-goog-api-key": credential} if profile.provider == ProviderType.GEMINI and credential else {}
        if profile.provider == ProviderType.DEEPSEEK and credential:
            headers["Authorization"] = f"Bearer {credential}"
        base_url = profile.base_url or {
            ProviderType.OLLAMA: "http://localhost:11434",
            ProviderType.DEEPSEEK: "https://api.deepseek.com",
            ProviderType.GEMINI: "https://generativelanguage.googleapis.com",
        }[profile.provider]
        endpoint = f"{base_url.rstrip('/')}/api/tags" if profile.provider == ProviderType.OLLAMA else base_url.rstrip("/")
        try:
            with httpx.Client(timeout=profile.request_timeout_seconds) as client:
                response = client.get(endpoint, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"{profile.provider.value} connection failed: {error}") from error
        return {"ok": True, "provider": profile.provider.value, "status_code": response.status_code}

    def ensure_project_profile(self, project_settings: ModelSettings, project_name: str = "") -> str:
        """Create the first global profile and migrate a legacy project credential."""
        settings = self.settings() if self.store.exists() else GlobalProviderSettings(config_version=2, active_profile="", profiles={})
        if settings.active_profile in settings.profiles:
            return settings.active_profile
        provider = project_settings.provider.lower()
        try:
            provider_type = ProviderType(provider)
        except ValueError:
            provider_type = ProviderType.OLLAMA
        profile_id = f"{provider}-default"
        if profile_id in settings.profiles:
            index = 2
            while f"{profile_id}-{index}" in settings.profiles:
                index += 1
            profile_id = f"{profile_id}-{index}"
        profile = ProviderProfile(
            provider=provider_type,
            base_url=project_settings.base_url,
            model=project_settings.name,
            request_timeout_seconds=project_settings.request_timeout_seconds,
            max_retries=project_settings.max_retries,
            options=project_settings.options.model_copy(),
            provider_options={
                **project_settings.provider_options,
                **{key: value for key, value in {"num_ctx": project_settings.options.num_ctx, "think": project_settings.options.think}.items() if value is not None},
            },
            credential_ref=profile_id,
        )
        settings.profiles[profile_id] = profile
        settings.active_profile = profile_id
        self.store.save(settings)
        self.credentials.migrate_legacy(profile_id, project_name, profile, project_settings.api_key.get_secret_value() if project_settings.api_key else None)
        return profile_id

    @staticmethod
    def _profile_from_data(data: dict[str, Any]) -> ProviderProfile:
        normalized = dict(data)
        normalized["provider"] = str(normalized.get("provider", "ollama")).lower()
        return ProviderProfile.model_validate(normalized)

    @classmethod
    def _validate_profile_id(cls, profile_id: str) -> None:
        if not cls.PROFILE_ID.fullmatch(profile_id):
            raise ValueError("Invalid provider profile id")

    @staticmethod
    def _get(settings: GlobalProviderSettings, profile_id: str) -> ProviderProfile:
        try:
            return settings.profiles[profile_id]
        except KeyError as error:
            raise ValueError(f"Unknown provider profile: {profile_id}") from error


__all__ = ["GlobalProviderService"]
