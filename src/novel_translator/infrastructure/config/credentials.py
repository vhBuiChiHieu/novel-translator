from __future__ import annotations

import os

from novel_translator.config import ProviderProfile, ProviderType


class ProviderCredentialStore:
    """Read/write provider credentials without ever serializing them to YAML."""

    service_name = "novel-translator"

    def _environment_name(self, profile: ProviderProfile) -> str | None:
        return {
            ProviderType.DEEPSEEK: "NOVEL_TRANSLATOR_DEEPSEEK_API_KEY",
            ProviderType.GEMINI: "NOVEL_TRANSLATOR_GEMINI_API_KEY",
        }.get(profile.provider)

    def get(self, profile_id: str, profile: ProviderProfile) -> str | None:
        environment_name = self._environment_name(profile)
        if environment_name and (value := os.getenv(environment_name)):
            return value
        try:
            import keyring

            return keyring.get_password(self.service_name, f"provider-profile:{profile_id}")
        except (ImportError, Exception):
            return None

    def set(self, profile_id: str, value: str) -> None:
        if not value:
            self.delete(profile_id)
            return
        try:
            import keyring

            keyring.set_password(self.service_name, f"provider-profile:{profile_id}", value)
        except ImportError as error:
            raise RuntimeError("Credential storage requires the desktop/keyring extra") from error

    def delete(self, profile_id: str) -> None:
        try:
            import keyring

            keyring.delete_password(self.service_name, f"provider-profile:{profile_id}")
        except Exception:
            pass

    def status(self, profile_id: str, profile: ProviderProfile) -> bool:
        return self.get(profile_id, profile) is not None

    def migrate_legacy(self, profile_id: str, project_name: str, profile: ProviderProfile, legacy_value: str | None = None) -> bool:
        if self.get(profile_id, profile):
            return False
        value = legacy_value
        if value is None:
            try:
                import keyring

                value = keyring.get_password(self.service_name, project_name)
            except Exception:
                value = None
        if value:
            self.set(profile_id, value)
            return True
        return False


__all__ = ["ProviderCredentialStore"]
