from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novel_translator.application.dtos import ModelCallDTO
from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import ModelCallORM, TranslationJobORM


class ModelCallQueryService:
    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = open_project_session(session, project_path)

    def list_calls(self, chunk_id: int | None = None) -> list[ModelCallDTO]:
        factory = create_session_factory(create_sqlite_engine(self.session.settings.database_path))
        with factory() as db_session:
            statement = (
                select(ModelCallORM)
                .join(TranslationJobORM, TranslationJobORM.id == ModelCallORM.translation_job_id)
                .where(TranslationJobORM.novel_id == self.session.novel.id)
            )
            if chunk_id is not None:
                statement = statement.where(ModelCallORM.translation_chunk_id == chunk_id)
            return [ModelCallDTO.model_validate(row) for row in db_session.scalars(statement.order_by(ModelCallORM.id))]

    def get_call(self, call_id: int) -> ModelCallDTO:
        row = next((call for call in self.list_calls() if call.id == call_id), None)
        if row is None:
            raise ValueError(f"Model call {call_id} was not found")
        return row
