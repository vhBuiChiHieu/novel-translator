from pathlib import Path

from sqlalchemy import select

from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import ChapterORM


class ExportService:
    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = session
        self.project_path = project_path

    def export(self) -> Path:
        active = open_project_session(self.session, self.project_path)
        settings = active.settings
        novel = active.novel
        sessions = create_session_factory(create_sqlite_engine(settings.database_path))
        with sessions() as session:
            chapters = list(
                session.scalars(
                    select(ChapterORM)
                    .where(ChapterORM.novel_id == novel.id, ChapterORM.translated_path.is_not(None))
                    .order_by(ChapterORM.chapter_number)
                )
            )
        text = "\n\n".join(
            (settings.project_path / chapter.translated_path).read_text(encoding="utf-8")
            for chapter in chapters
            if chapter.translated_path
        )
        output = settings.project_path / "exports" / "novel.txt"
        output.write_text(text, encoding="utf-8")
        return output
