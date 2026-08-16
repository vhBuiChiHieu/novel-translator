from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator

from novel_translator.domain.model.enums import ProviderType


class ChunkSettings(BaseModel):
    target_chars: int = 6000
    max_chars: int = 10000
    min_chars: int = 2000


class ContinuitySettings(BaseModel):
    include_previous_tail: bool = True
    previous_tail_paragraphs: int = 3


class TranslationSettings(BaseModel):
    prompt_version: Literal["translation-v1", "translation-v2"] = "translation-v1"


class CommonModelOptions(BaseModel):
    """Options shared by provider APIs."""

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None


class ModelOptions(CommonModelOptions):
    """Provider tuning values, all optional so the provider can use its own defaults."""

    num_ctx: int | None = None
    think: bool | None = None


class ModelSettings(BaseModel):
    """Legacy project-scoped model settings kept for migration compatibility."""

    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    name: str = "qwen3:14b"
    request_timeout_seconds: int = 300
    max_retries: int = 2
    options: ModelOptions = Field(default_factory=ModelOptions)
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    provider_options: dict[str, Any] = Field(default_factory=dict)


class ProviderProfile(BaseModel):
    """Application-level provider configuration.

    ``api_key`` is intentionally excluded and exists only as an in-memory bridge
    for the provider factory. It is never written to YAML or returned by an API.
    """

    provider: ProviderType
    base_url: str | None = None
    model: str = "qwen3:14b"
    request_timeout_seconds: int = 300
    max_retries: int = 2
    options: CommonModelOptions = Field(default_factory=CommonModelOptions)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    credential_ref: str | None = None
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @field_validator("provider_options")
    @classmethod
    def reject_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        sensitive = {"api_key", "apikey", "authorization", "secret", "token", "password"}

        def visit(item: Any) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if str(key).lower() in sensitive:
                        raise ValueError("Provider options must not contain credentials")
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)

        visit(value)
        return value

    def with_credential(self, credential: str | None) -> ProviderProfile:
        return self.model_copy(update={"api_key": SecretStr(credential) if credential else None})

    def to_legacy(self) -> ModelSettings:
        base_url = self.base_url
        if base_url is None:
            base_url = {
                ProviderType.OLLAMA: "http://localhost:11434",
                ProviderType.DEEPSEEK: "https://api.deepseek.com",
                ProviderType.GEMINI: "https://generativelanguage.googleapis.com",
            }[self.provider]
        options = ModelOptions(
            temperature=self.options.temperature,
            top_p=self.options.top_p,
            top_k=self.options.top_k,
            max_output_tokens=self.options.max_output_tokens,
            num_ctx=self.provider_options.get("num_ctx"),
            think=self.provider_options.get("think"),
        )
        return ModelSettings(
            provider=self.provider.value,
            base_url=base_url,
            name=self.model,
            request_timeout_seconds=self.request_timeout_seconds,
            max_retries=self.max_retries,
            options=options,
            api_key=self.api_key,
            provider_options=self.provider_options,
        )


class GlobalProviderSettings(BaseModel):
    config_version: int = 2
    active_profile: str = "ollama-local"
    profiles: dict[str, ProviderProfile] = Field(default_factory=dict)


def default_global_provider_settings() -> GlobalProviderSettings:
    return GlobalProviderSettings(
        active_profile="ollama-local",
        profiles={
            "ollama-local": ProviderProfile(
                provider=ProviderType.OLLAMA,
                base_url="http://localhost:11434",
                model="qwen3:14b",
            )
        },
    )


def provider_profile_hash(profile: ProviderProfile) -> str:
    """Return a stable, secret-free fingerprint for job snapshots."""
    payload = profile.model_dump(exclude={"api_key"}, mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ContextAutoConfirmSettings(BaseModel):
    character: bool = True
    term: bool = True
    location: bool = True
    organization: bool = True
    addressing: bool = False
    relationship: bool = False
    world_fact: bool = False


class ContextSettings(BaseModel):
    relation_depth: int = 1
    max_characters_per_request: int = 30
    max_terms_per_request: int = 50
    max_relationships_per_request: int = 30
    max_facts_per_request: int = 20
    auto_confirm: ContextAutoConfirmSettings = Field(default_factory=ContextAutoConfirmSettings)
    minimum_confidence: float = 0.90


class ValidationSettings(BaseModel):
    min_length_ratio: float = 0.25
    max_length_ratio: float = 4.0
    max_context_updates: int = 100


class ProjectSettings(BaseModel):
    project_name: str
    title: str = ""
    source_language: str = "zh"
    target_language: str = "vi"
    genre: list[str] = Field(default_factory=lambda: ["xianxia"])
    model: ModelSettings = Field(default_factory=ModelSettings)
    prompt_version: Literal["translation-v1", "translation-v2"] = "translation-v1"
    chunk: ChunkSettings = Field(default_factory=ChunkSettings)
    continuity: ContinuitySettings = Field(default_factory=ContinuitySettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    log_level: str = "INFO"

    project_path: Path = Field(default=Path("."), exclude=True)

    @property
    def database_path(self) -> Path:
        return self.project_path / "data" / "novel.db"


def default_yaml(project_name: str) -> dict[str, Any]:
    return {
        "project": {"name": project_name},
        "novel": {"title": "", "source_language": "zh", "target_language": "vi"},
        "genre": ["xianxia"],
        "model": ModelSettings().model_dump(exclude_none=True),
        "translation": {
            "prompt_version": TranslationSettings().prompt_version,
            "chunk": ChunkSettings().model_dump(),
            "continuity": ContinuitySettings().model_dump(),
        },
        "context": {**ContextSettings().model_dump(exclude={"minimum_confidence"}), "minimum_confidence": {"auto_confirm": 0.90}},
        "validation": ValidationSettings().model_dump(),
        "log_level": "INFO",
    }


def load_project_settings(
    project_path: Path,
    overrides: dict[str, Any] | None = None,
    *,
    use_global: bool = False,
) -> ProjectSettings:
    config_path = project_path / "novel.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"No novel.yaml in current directory: {project_path}")
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    # Credentials are accepted only from the environment, never project configuration.
    model_raw = {key: value for key, value in raw.get("model", {}).items() if key != "api_key"}
    translation_raw = raw.get("translation", {})
    context_raw = dict(raw.get("context", {}))
    minimum = context_raw.pop("minimum_confidence", {})
    if isinstance(minimum, dict):
        context_raw["minimum_confidence"] = minimum.get("auto_confirm", 0.90)
    data: dict[str, Any] = {
        "project_name": raw.get("project", {}).get("name", project_path.name),
        "title": raw.get("novel", {}).get("title", ""),
        "source_language": raw.get("novel", {}).get("source_language", "zh"),
        "target_language": raw.get("novel", {}).get("target_language", "vi"),
        "genre": raw.get("genre", ["xianxia"]),
        "model": model_raw,
        "prompt_version": translation_raw.get("prompt_version", "translation-v1"),
        "chunk": translation_raw.get("chunk", {}),
        "continuity": translation_raw.get("continuity", {}),
        "context": context_raw,
        "validation": raw.get("validation", {}),
        "log_level": os.getenv("NOVEL_TRANSLATOR_LOG_LEVEL", raw.get("log_level", "INFO")),
        "project_path": project_path,
    }
    if value := os.getenv("NOVEL_TRANSLATOR_OLLAMA_URL"):
        data["model"] = {**model_raw, "base_url": value}
    if value := os.getenv("NOVEL_TRANSLATOR_MODEL"):
        data["model"] = {**data["model"], "name": value}
    if use_global:
        try:
            from novel_translator.infrastructure.config.credentials import ProviderCredentialStore
            from novel_translator.infrastructure.config.store import GlobalSettingsStore

            store = GlobalSettingsStore()
            if store.exists():
                global_settings = store.load()
                profile = global_settings.profiles.get(global_settings.active_profile)
                if profile is not None:
                    credential = ProviderCredentialStore().get(global_settings.active_profile, profile)
                    data["model"] = profile.to_legacy().model_dump(exclude_none=True, mode="python")
                    if credential:
                        data["model"]["api_key"] = credential
        except (ImportError, OSError, ValueError):
            # Global settings are optional during the compatibility period.
            pass
    provider_name = str(data["model"].get("provider", "ollama")).lower()
    if provider_name == "ollama" and (value := os.getenv("NOVEL_TRANSLATOR_OLLAMA_URL")):
        data["model"] = {**data["model"], "base_url": value}
    if value := os.getenv("NOVEL_TRANSLATOR_MODEL"):
        data["model"] = {**data["model"], "name": value}
    if provider_name == "deepseek" and (value := os.getenv("NOVEL_TRANSLATOR_DEEPSEEK_API_KEY")):
        data["model"] = {**data["model"], "api_key": value}
    elif provider_name == "gemini" and (value := os.getenv("NOVEL_TRANSLATOR_GEMINI_API_KEY")):
        data["model"] = {**data["model"], "api_key": value}
    elif provider_name in {"deepseek", "gemini"}:
        # keyring is optional for CLI-only installations. Missing keyring support
        # simply preserves the existing environment-variable behavior.
        try:
            import keyring

            stored_key = keyring.get_password("novel-translator", data["project_name"])
        except Exception:
            stored_key = None
        if stored_key:
            data["model"] = {**data["model"], "api_key": stored_key}
    if overrides:
        data.update({key: value for key, value in overrides.items() if value is not None})
    return ProjectSettings.model_validate(data)
