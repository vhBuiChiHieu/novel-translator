from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr


class ChunkSettings(BaseModel):
    target_chars: int = 6000
    max_chars: int = 10000
    min_chars: int = 2000


class ContinuitySettings(BaseModel):
    include_previous_tail: bool = True
    previous_tail_paragraphs: int = 3


class ModelOptions(BaseModel):
    temperature: float = 0.2
    top_p: float = 0.9
    num_ctx: int = 16384
    think: bool = False


class ModelSettings(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    name: str = "qwen3:14b"
    request_timeout_seconds: int = 300
    max_retries: int = 2
    options: ModelOptions = Field(default_factory=ModelOptions)
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)


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
        "model": ModelSettings().model_dump(),
        "translation": {"prompt_version": "translation-v1", "chunk": ChunkSettings().model_dump(), "continuity": ContinuitySettings().model_dump()},
        "context": {**ContextSettings().model_dump(exclude={"minimum_confidence"}), "minimum_confidence": {"auto_confirm": 0.90}},
        "validation": ValidationSettings().model_dump(),
    }


def load_project_settings(project_path: Path, overrides: dict[str, Any] | None = None) -> ProjectSettings:
    config_path = project_path / "novel.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"No novel.yaml in current directory: {project_path}")
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    # Credentials are accepted only from the environment, never project configuration.
    model_raw = {key: value for key, value in raw.get("model", {}).items() if key != "api_key"}
    translation_raw = raw.get("translation", {})
    context_raw = raw.get("context", {})
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
        "chunk": translation_raw.get("chunk", {}),
        "continuity": translation_raw.get("continuity", {}),
        "context": context_raw,
        "validation": raw.get("validation", {}),
        "log_level": os.getenv("NOVEL_TRANSLATOR_LOG_LEVEL", "INFO"),
        "project_path": project_path,
    }
    if value := os.getenv("NOVEL_TRANSLATOR_OLLAMA_URL"):
        data["model"] = {**model_raw, "base_url": value}
    if value := os.getenv("NOVEL_TRANSLATOR_MODEL"):
        data["model"] = {**data["model"], "name": value}
    if value := os.getenv("NOVEL_TRANSLATOR_DEEPSEEK_API_KEY"):
        data["model"] = {**data["model"], "api_key": value}
    if overrides:
        data.update({key: value for key, value in overrides.items() if value is not None})
    return ProjectSettings.model_validate(data)
