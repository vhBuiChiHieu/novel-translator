from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from novel_translator.config import GlobalProviderSettings, default_global_provider_settings


class GlobalSettingsStore:
    """Persist application-level provider profiles outside a project."""

    filename = "settings.yaml"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        try:
            from platformdirs import user_config_path

            return Path(user_config_path("NovelTranslator", appauthor=False)) / "settings.yaml"
        except ImportError:
            # Keep CLI-only installations usable when optional dependencies are absent.
            if os.name == "nt" and os.getenv("APPDATA"):
                return Path(os.environ["APPDATA"] or "") / "NovelTranslator" / "settings.yaml"
            return Path.home() / ".config" / "NovelTranslator" / "settings.yaml"

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> GlobalProviderSettings:
        if not self.exists():
            return default_global_provider_settings()
        with self.path.open("r", encoding="utf-8") as stream:
            raw: Any = yaml.safe_load(stream) or {}
        return GlobalProviderSettings.model_validate(raw)

    def save(self, settings: GlobalProviderSettings) -> GlobalProviderSettings:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump(mode="json", exclude_none=True)
        with self.path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(payload, stream, allow_unicode=True, sort_keys=False)
        return settings


__all__ = ["GlobalSettingsStore"]
