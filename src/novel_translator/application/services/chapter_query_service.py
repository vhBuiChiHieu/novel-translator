from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novel_translator.application.dtos import ChapterDTO, ChapterPreviewDTO
from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.domain.translation.chunker import normalize_source
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import ChapterORM


class ChapterQueryService:
    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = open_project_session(session, project_path)

    def list_chapters(self, status: str | None = None) -> list[ChapterDTO]:
        factory = create_session_factory(create_sqlite_engine(self.session.settings.database_path))
        with factory() as db_session:
            statement = select(ChapterORM).where(ChapterORM.novel_id == self.session.novel.id)
            if status:
                statement = statement.where(ChapterORM.status == status)
            chapters = list(db_session.scalars(statement.order_by(ChapterORM.chapter_number)))
            return [ChapterDTO.model_validate(chapter) for chapter in chapters]

    def get_chapter(self, chapter_number: int) -> ChapterDTO:
        chapter = next((row for row in self.list_chapters() if row.chapter_number == chapter_number), None)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_number} was not imported")
        source = self.session.project_path / chapter.source_path
        return chapter.model_copy(update={"source_text": source.read_text(encoding="utf-8")})

    def preview_file(self, path: Path, chapter_number: int) -> ChapterPreviewDTO:
        try:
            source = normalize_source(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            return ChapterPreviewDTO(
                chapter_number=chapter_number,
                path=path,
                valid_utf8=False,
                error=f"Chapter is not valid UTF-8: {error}",
            )
        return ChapterPreviewDTO(chapter_number=chapter_number, path=path, valid_utf8=True, source_text=source)
