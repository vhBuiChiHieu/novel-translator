from pathlib import Path

import pytest
from sqlalchemy import select

from novel_translator.application.services.import_service import ImportService
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.services.translation_service import TranslationService
from novel_translator.config import load_project_settings
from novel_translator.infrastructure.model.exceptions import ModelProviderError
from novel_translator.infrastructure.model.provider import ProviderDiagnostic, ProviderMetrics
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import (
    EntityORM,
    ModelCallORM,
    TranslationChunkORM,
    TranslationJobORM,
)
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


class FakeProvider:
    last_metrics = ProviderMetrics(prompt_tokens=4, output_tokens=2, duration_ms=10)
    last_diagnostic = None

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(translation="Bản dịch tiếng Việt có nội dung hợp lệ.")


class RecordingProvider(FakeProvider):
    def __init__(self) -> None:
        self.requests: list[TranslationRequest] = []

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.requests.append(request)
        return TranslationResponse(
            translation="Lục Trầm tới Tiểu Hàn Thành.",
            context_updates=[
                {
                    "type": "character",
                    "source": "陆沉",
                    "translation": "Lục Trầm",
                    "confidence": 0.98,
                }
            ],
        )


class FailingProvider:
    last_metrics = ProviderMetrics()
    last_diagnostic = ProviderDiagnostic(
        provider="fake",
        message="Fake response rejected",
        status_code=502,
        body={"error": "unavailable"},
    )

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise ModelProviderError("Fake response rejected")


def test_translation_persists_chunk_and_resumes_without_retranslation(
    tmp_path: Path, monkeypatch
) -> None:
    project = ProjectService().init(tmp_path, "demo")
    external = tmp_path / "chapters"
    external.mkdir()
    (external / "chapter_0001.txt").write_text(
        "这是第一章的内容。这里还有更多中文文本用于验证翻译流程。", encoding="utf-8"
    )
    monkeypatch.chdir(project)
    ImportService().import_directory(external)

    provider = FakeProvider()
    job = TranslationService(provider).translate(1)
    assert job.status == "completed"
    assert (project / "translated" / "chapter_0001.txt").is_file()

    settings = load_project_settings(project)
    with create_session_factory(create_sqlite_engine(settings.database_path))() as session:
        chunks = list(session.scalars(select(TranslationChunkORM)))
    assert len(chunks) == 1
    assert chunks[0].status == "completed"
    assert chunks[0].context_snapshot_json == ContextSnapshot().model_dump()

    # A completed job remains immutable; callers must use --force for a new job.
    assert job.total_prompt_tokens == 4


def test_translation_persists_failure_diagnostic_and_progress(
    tmp_path: Path, monkeypatch
) -> None:
    project = ProjectService().init(tmp_path, "demo")
    external = tmp_path / "chapters"
    external.mkdir()
    (external / "chapter_0001.txt").write_text("这是第一章的内容。", encoding="utf-8")
    monkeypatch.chdir(project)
    ImportService().import_directory(external)
    progress = []

    with pytest.raises(ModelProviderError, match="Fake response rejected"):
        TranslationService(FailingProvider()).translate(1, on_progress=progress.append)

    settings = load_project_settings(project)
    with create_session_factory(create_sqlite_engine(settings.database_path))() as session:
        chunk = session.scalar(select(TranslationChunkORM))
        assert chunk is not None
        assert chunk.status == "failed"
        assert chunk.error_message == "Fake response rejected"
        assert chunk.raw_model_response_json == {
            "provider": "fake",
            "message": "Fake response rejected",
            "status_code": 502,
            "body": {"error": "unavailable"},
            "truncated": False,
        }
    assert [event.event for event in progress] == ["job_started", "chunk_started", "chunk_failed"]


def test_translation_uses_configured_v2_prompt_and_records_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    project = ProjectService().init(tmp_path, "demo")
    config_path = project / "novel.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("prompt_version: translation-v1", "prompt_version: translation-v2"),
        encoding="utf-8",
    )
    external = tmp_path / "chapters"
    external.mkdir()
    (external / "chapter_0001.txt").write_text("陆沉来到小寒城。", encoding="utf-8")
    monkeypatch.chdir(project)
    ImportService().import_directory(external)

    provider = RecordingProvider()
    TranslationService(provider).translate(1)

    assert len(provider.requests) == 1
    assert "## RESPONSE FORMAT" in provider.requests[0].user_prompt
    assert "Never emit a key with a null value" in provider.requests[0].user_prompt
    settings = load_project_settings(project)
    with create_session_factory(create_sqlite_engine(settings.database_path))() as session:
        job = session.scalar(select(TranslationJobORM))
        entity = session.scalar(select(EntityORM))
        chunk = session.scalar(select(TranslationChunkORM))
        model_call = session.scalar(select(ModelCallORM))
    assert job is not None
    assert job.prompt_version == "translation-v2"
    assert entity is not None
    assert entity.prompt_version == "translation-v2"
    assert chunk is not None
    assert model_call is not None
    update = chunk.raw_model_response_json["context_updates"][0]
    assert update == {
        "type": "character",
        "source": "陆沉",
        "translation": "Lục Trầm",
        "aliases": [],
        "related_entities": [],
        "confidence": 0.98,
    }
    assert model_call.response_json == chunk.raw_model_response_json


def test_resume_uses_persisted_prompt_version_after_configuration_changes(
    tmp_path: Path, monkeypatch
) -> None:
    project = ProjectService().init(tmp_path, "demo")
    external = tmp_path / "chapters"
    external.mkdir()
    (external / "chapter_0001.txt").write_text("陆沉来到小寒城。", encoding="utf-8")
    monkeypatch.chdir(project)
    ImportService().import_directory(external)

    with pytest.raises(ModelProviderError):
        TranslationService(FailingProvider()).translate(1)
    config_path = project / "novel.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("prompt_version: translation-v1", "prompt_version: translation-v2"),
        encoding="utf-8",
    )

    provider = RecordingProvider()
    TranslationService(provider).translate(1, resume=True)

    assert len(provider.requests) == 1
    assert "## RESPONSE FORMAT" not in provider.requests[0].user_prompt
    settings = load_project_settings(project)
    with create_session_factory(create_sqlite_engine(settings.database_path))() as session:
        job = session.scalar(select(TranslationJobORM))
    assert job is not None
    assert job.prompt_version == "translation-v1"
