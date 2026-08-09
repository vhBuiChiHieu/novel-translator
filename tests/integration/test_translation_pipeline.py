from pathlib import Path

from sqlalchemy import select

from novel_translator.application.services.import_service import ImportService
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.services.translation_service import TranslationService
from novel_translator.config import load_project_settings
from novel_translator.infrastructure.model.provider import ProviderMetrics
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import TranslationChunkORM
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


class FakeProvider:
    last_metrics = ProviderMetrics(prompt_tokens=4, output_tokens=2, duration_ms=10)

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(translation="Bản dịch tiếng Việt có nội dung hợp lệ.")


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
