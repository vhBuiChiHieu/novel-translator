from __future__ import annotations

import hashlib

import httpx

from novel_translator.config import provider_profile_hash
from novel_translator.infrastructure.config.credentials import ProviderCredentialStore
from novel_translator.infrastructure.config.store import GlobalSettingsStore
from novel_translator.infrastructure.model.factory import create_model_provider
from novel_translator.infrastructure.model.provider import ModelProvider


class ProviderResolver:
    """Resolve and cache one immutable provider snapshot per operation."""

    def __init__(
        self,
        store: GlobalSettingsStore | None = None,
        credentials: ProviderCredentialStore | None = None,
    ) -> None:
        self.store = store or GlobalSettingsStore()
        self.credentials = credentials or ProviderCredentialStore()
        self._cache: dict[tuple[str, str, str], ModelProvider] = {}

    def resolve(self, profile_id: str | None = None, client: httpx.Client | None = None) -> ModelProvider:
        settings = self.store.load()
        selected = profile_id or settings.active_profile
        profile = settings.profiles.get(selected)
        if profile is None:
            raise ValueError(f"Unknown active provider profile: {selected}")
        fingerprint = provider_profile_hash(profile)
        credential = self.credentials.get(selected, profile)
        credential_fingerprint = hashlib.sha256((credential or "").encode("utf-8")).hexdigest()
        cache_key = (selected, fingerprint, credential_fingerprint)
        if client is None and cache_key in self._cache:
            return self._cache[cache_key]
        provider = create_model_provider(profile.with_credential(credential), client)
        setattr(provider, "profile_id", selected)
        setattr(provider, "config_hash", fingerprint)
        if client is None:
            self._cache[cache_key] = provider
        return provider

    def invalidate(self, profile_id: str | None = None) -> None:
        if profile_id is None:
            self._cache.clear()
            return
        for key in list(self._cache):
            if key[0] == profile_id:
                del self._cache[key]


__all__ = ["ProviderResolver"]
