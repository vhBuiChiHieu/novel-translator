from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_translator.application.dtos import NovelDTO


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class BootstrapResponse(BaseModel):
    authenticated: bool = True


class CurrentProjectResponse(BaseModel):
    open: bool
    project: NovelDTO | None = None
    path: str | None = None
    validation_errors: list[str] = Field(default_factory=list)


class ProjectPathRequest(BaseModel):
    path: str


class DirectoryPickerRequest(BaseModel):
    purpose: Literal["project", "parent", "source"] = "project"


class CreateProjectRequest(BaseModel):
    parent_path: str
    name: str = Field(min_length=1, max_length=128)


class ResetRequest(BaseModel):
    confirm: Literal[True]


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="allow")


class ApiKeyRequest(BaseModel):
    api_key: str = Field(default="", json_schema_extra={"writeOnly": True})


class ApiKeyStatus(BaseModel):
    configured: bool


class ProviderProfileRequest(BaseModel):
    profile_id: str | None = None
    provider: str = "ollama"
    base_url: str | None = None
    model: str = "qwen3:14b"
    request_timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=2, ge=0)
    options: dict[str, Any] = Field(default_factory=dict)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    credential_ref: str | None = None


class ProviderProfilePatch(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    request_timeout_seconds: int | None = Field(default=None, ge=1)
    max_retries: int | None = Field(default=None, ge=0)
    options: dict[str, Any] | None = None
    provider_options: dict[str, Any] | None = None
    credential_ref: str | None = None


class ProviderCredentialRequest(BaseModel):
    api_key: str = Field(default="", json_schema_extra={"writeOnly": True})


class ImportRequest(BaseModel):
    source_directory: str


class ImportPreviewRequest(ImportRequest):
    pass


class TranslationRequest(BaseModel):
    chapter_number: int = Field(ge=1)
    resume: bool = False
    force: bool = False


class TranslationRangeRequest(BaseModel):
    first: int = Field(ge=1)
    last: int = Field(ge=1)
    resume: bool = False
    force: bool = False


class ContextRequest(BaseModel):
    context_type: Literal["character", "location", "organization", "term"]
    source: str = Field(min_length=1)
    translation: str | None = None
    description: str | None = None
    status: Literal["confirmed", "proposed"] = "confirmed"


class ConflictResolveRequest(BaseModel):
    action: Literal["existing", "candidate", "custom"]
    value: str | None = None


class ExportRequest(BaseModel):
    kind: Literal["novel", "context"] = "novel"


class OperationResponse(BaseModel):
    operation_id: str
    status: str
    chapter_numbers: list[int] = Field(default_factory=list)


class OperationView(BaseModel):
    operation_id: str
    kind: str
    status: str
    chapter_numbers: list[int] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class CancelResponse(BaseModel):
    operation_id: str
    status: str
    message: str
