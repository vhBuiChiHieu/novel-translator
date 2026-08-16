from pathlib import Path

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
