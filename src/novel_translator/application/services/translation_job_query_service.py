from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novel_translator.application.dtos import TranslationChunkDTO, TranslationJobDTO
from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import (
    ChapterORM,
    TranslationChunkORM,
    TranslationJobORM,
)


class TranslationJobQueryService:
    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = open_project_session(session, project_path)

    def list_jobs(self, chapter_number: int | None = None) -> list[TranslationJobDTO]:
        factory = create_session_factory(create_sqlite_engine(self.session.settings.database_path))
        with factory() as db_session:
            statement = (
                select(TranslationJobORM, ChapterORM.chapter_number)
                .join(ChapterORM, ChapterORM.id == TranslationJobORM.chapter_id)
                .where(TranslationJobORM.novel_id == self.session.novel.id)
            )
            if chapter_number is not None:
                statement = statement.where(ChapterORM.chapter_number == chapter_number)
            return [
                TranslationJobDTO.model_validate(job).model_copy(update={"chapter_number": number})
                for job, number in db_session.execute(statement.order_by(TranslationJobORM.id.desc()))
            ]

    def get_chunk_detail(self, chunk_id: int) -> TranslationChunkDTO:
        factory = create_session_factory(create_sqlite_engine(self.session.settings.database_path))
        with factory() as db_session:
            chunk = db_session.scalar(
                select(TranslationChunkORM)
                .join(TranslationJobORM, TranslationJobORM.id == TranslationChunkORM.translation_job_id)
                .where(TranslationChunkORM.id == chunk_id, TranslationJobORM.novel_id == self.session.novel.id)
            )
            if chunk is None:
                raise ValueError(f"Translation chunk {chunk_id} was not found")
            return TranslationChunkDTO.model_validate(chunk)
