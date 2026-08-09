from pathlib import Path

from sqlalchemy import select

from novel_translator.application.services.import_service import ImportService
from novel_translator.application.services.project_service import ProjectService
from novel_translator.config import load_project_settings
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import ChapterORM


def test_init_migrates_and_imports_chapters(tmp_path: Path, monkeypatch) -> None:
    project = ProjectService().init(tmp_path, "demo")
    external = tmp_path / "chapters"
    external.mkdir()
    (external / "chapter_0002.txt").write_text("第二章", encoding="utf-8")
    (external / "chapter_0001.txt").write_text("第一章", encoding="utf-8")
    monkeypatch.chdir(project)
    assert ImportService().import_directory(external) == 2
    settings = load_project_settings(project)
    with create_session_factory(create_sqlite_engine(settings.database_path))() as session:
        chapters = list(session.scalars(select(ChapterORM).order_by(ChapterORM.chapter_number)))
    assert [chapter.chapter_number for chapter in chapters] == [1, 2]
    assert (project / "source" / "chapter_0001.txt").exists()
