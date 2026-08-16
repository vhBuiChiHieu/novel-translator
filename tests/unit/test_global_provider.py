from pathlib import Path

import httpx

from novel_translator.application.services.global_provider_service import GlobalProviderService
from novel_translator.config import ModelSettings, ProviderType
from novel_translator.infrastructure.config.store import GlobalSettingsStore
from novel_translator.infrastructure.model.resolver import ProviderResolver


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, profile_id, profile):
        return self.values.get(profile_id)

    def set(self, profile_id, value):
        self.values[profile_id] = value

    def delete(self, profile_id):
        self.values.pop(profile_id, None)

    def status(self, profile_id, profile):
        return profile_id in self.values

    def migrate_legacy(self, profile_id, project_name, profile, legacy_value=None):
        if legacy_value:
            self.values[profile_id] = legacy_value
            return True
        return False


def test_global_store_round_trips_without_secret(tmp_path: Path) -> None:
    store = GlobalSettingsStore(tmp_path / "settings.yaml")
    service = GlobalProviderService(store=store, credentials=MemoryCredentials())

    service.create("gemini-default", {"provider": "gemini", "model": "gemini-2.5-flash"})
    service.set_credential("gemini-default", "secret-token")

    assert "secret-token" not in (tmp_path / "settings.yaml").read_text(encoding="utf-8")
    assert service.settings().profiles["gemini-default"].provider == ProviderType.GEMINI
    assert service.credential_status("gemini-default") == {"configured": True}


def test_legacy_profile_migration_and_resolver_cache(tmp_path: Path) -> None:
    store = GlobalSettingsStore(tmp_path / "settings.yaml")
    credentials = MemoryCredentials()
    service = GlobalProviderService(store=store, credentials=credentials)
    profile_id = service.ensure_project_profile(
        ModelSettings(provider="gemini", name="gemini-2.5-flash"), "old-project"
    )
    credentials.set(profile_id, "secret-token")
    resolver = ProviderResolver(store=store, credentials=credentials)

    first = resolver.resolve()
    second = resolver.resolve()
    assert first is second
    assert getattr(first, "profile_id") == profile_id
    resolver.invalidate(profile_id)
    assert resolver.resolve() is not first


def test_delete_last_custom_profile_restores_default_ollama(tmp_path: Path) -> None:
    store = GlobalSettingsStore(tmp_path / "settings.yaml")
    credentials = MemoryCredentials()
    service = GlobalProviderService(store=store, credentials=credentials)

    service.create("legacy", {"provider": "deepseek", "model": "test-model"})
    service.set_credential("legacy", "secret-token")
    service.delete("legacy")

    settings = service.settings()
    assert settings.active_profile == "ollama-local"
    assert settings.profiles["ollama-local"].provider == ProviderType.OLLAMA
    assert settings.profiles["ollama-local"].model == "qwen3:14b"
    assert "legacy" not in credentials.values


def test_ensure_project_profile_reuses_existing_profile_when_active_id_is_stale(tmp_path: Path) -> None:
    store = GlobalSettingsStore(tmp_path / "settings.yaml")
    credentials = MemoryCredentials()
    service = GlobalProviderService(store=store, credentials=credentials)

    service.create("shared-deepseek", {"provider": "deepseek", "model": "test-model"})
    settings = service.settings()
    settings.active_profile = "stale-profile-id"
    store.save(settings)

    profile_id = service.ensure_project_profile(ModelSettings(provider="ollama", name="qwen3:14b"), "new-project")

    assert profile_id == "shared-deepseek"
    assert service.settings().active_profile == "shared-deepseek"
    assert list(service.settings().profiles) == ["shared-deepseek"]


def test_gemini_connection_checks_selected_model(monkeypatch, tmp_path: Path) -> None:
    store = GlobalSettingsStore(tmp_path / "settings.yaml")
    credentials = MemoryCredentials()
    service = GlobalProviderService(store=store, credentials=credentials)
    service.create(
        "gemini-default",
        {"provider": "gemini", "model": "gemini-3.7-flash", "base_url": "https://generativelanguage.googleapis.com"},
    )
    service.set_credential("gemini-default", "secret-token")
    calls: list[tuple[str, dict[str, str]]] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, endpoint: str, headers: dict[str, str]):
            calls.append((endpoint, headers))
            return httpx.Response(200, request=httpx.Request("GET", endpoint))

    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: FakeClient())

    assert service.test_connection("gemini-default") == {"ok": True, "provider": "gemini", "status_code": 200}
    assert calls == [
        (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash",
            {"x-goog-api-key": "secret-token"},
        )
    ]
