from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import MetaData, Table, inspect, select

from novel_translator.application.dtos import (
    ChapterDTO,
    ChapterPreviewDTO,
    ConflictDTO,
    ContextItemDTO,
    DashboardDTO,
    DatabaseTableDTO,
    ModelCallDTO,
    TranslationChunkDTO,
    TranslationJobDTO,
)
from novel_translator.application.services.chapter_query_service import ChapterQueryService
from novel_translator.application.services.config_service import ConfigService
from novel_translator.application.services.context_service import ContextService
from novel_translator.application.services.export_service import ExportService
from novel_translator.application.services.import_service import ImportService
from novel_translator.application.services.model_call_query_service import ModelCallQueryService
from novel_translator.application.services.project_health_service import ProjectHealthService
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.services.translation_job_query_service import TranslationJobQueryService
from novel_translator.application.services.translation_service import TranslationProgress, TranslationService
from novel_translator.application.session import ProjectSession
from novel_translator.config import ProjectSettings
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import (
    EntityORM,
    TerminologyORM,
)


class ApplicationFacade:
    """The UI-facing application API. It never exposes SQLAlchemy objects."""

    def __init__(self, project_path: Path | None = None) -> None:
        self._session: ProjectSession | None = None
        if project_path is not None:
            self.open_project(project_path)

    @property
    def session(self) -> ProjectSession:
        if self._session is None:
            raise RuntimeError("No project is open")
        return self._session

    def open_project(self, project_path: Path) -> ProjectSession:
        self._session = ProjectService().open_session(project_path)
        return self._session

    def reset_project(self) -> ProjectSession:
        """Reset project data and reopen the project with its existing configuration."""
        project_path = self.session.project_path
        ProjectService().reset(project_path)
        self._session = ProjectService().open_session(project_path)
        return self._session

    def get_dashboard(self) -> DashboardDTO:
        session = self.session
        chapters = ChapterQueryService(session).list_chapters()
        jobs = TranslationJobQueryService(session).list_jobs()
        open_conflicts = len([row for row in ContextService(session).conflicts() if row.status == "open"])
        errors = ProjectHealthService().check(session.project_path)
        return DashboardDTO(
            project=session.novel,
            project_path=session.project_path,
            provider=session.settings.model.provider,
            model=session.settings.model.name,
            chapter_counts={
                "total": len(chapters),
                "imported": sum(chapter.status == "imported" for chapter in chapters),
                "translated": sum(chapter.status == "translated" for chapter in chapters),
                "failed": sum(job.status in {"failed", "partial"} for job in jobs),
            },
            running_jobs=[job for job in jobs if job.status == "running"],
            open_conflicts=open_conflicts,
            health_ok=not errors,
            health_errors=errors,
        )

    def update_settings(self, updates: dict[str, object]) -> ProjectSettings:
        service = ConfigService(self.session)
        settings = service.update(updates)
        self._session = service.session
        return settings

    def set_api_key(self, api_key: str) -> None:
        service = ConfigService(self.session)
        service.set_api_key(api_key)
        self._session = service.session

    def preview_import(self, source_directory: Path) -> list[ChapterPreviewDTO]:
        return ImportService.preview_directory(source_directory)

    def import_chapters(self, source_directory: Path) -> int:
        return ImportService(self.session).import_directory(source_directory)

    def list_chapters(self, status: str | None = None) -> list[ChapterDTO]:
        return ChapterQueryService(self.session).list_chapters(status)

    def get_chapter(self, chapter_number: int) -> ChapterDTO:
        return ChapterQueryService(self.session).get_chapter(chapter_number)

    def translate(
        self,
        chapter_number: int,
        *,
        resume: bool = False,
        force: bool = False,
        on_progress: Callable[[TranslationProgress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranslationJobDTO:
        # Pick up environment/keyring changes made while the desktop app is open.
        self._session = ProjectSession.open(self.session.project_path)
        job = TranslationService(session=self.session).translate(
            chapter_number,
            resume=resume,
            force=force,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )
        return next(row for row in self.list_jobs(chapter_number) if row.id == job.id)

    def translate_range(
        self,
        first: int,
        last: int,
        *,
        resume: bool = False,
        force: bool = False,
        on_progress: Callable[[TranslationProgress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[TranslationJobDTO]:
        return [
            self.translate(
                chapter,
                resume=resume,
                force=force,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )
            for chapter in range(first, last + 1)
        ]

    def list_jobs(self, chapter_number: int | None = None) -> list[TranslationJobDTO]:
        return TranslationJobQueryService(self.session).list_jobs(chapter_number)

    def get_chunk_detail(self, chunk_id: int) -> TranslationChunkDTO:
        return TranslationJobQueryService(self.session).get_chunk_detail(chunk_id)

    def list_model_calls(self, chunk_id: int | None = None) -> list[ModelCallDTO]:
        return ModelCallQueryService(self.session).list_calls(chunk_id)

    def list_context(self, context_type: str | None = None, status: str | None = None) -> list[ContextItemDTO]:
        factory = create_session_factory(create_sqlite_engine(self.session.settings.database_path))
        rows: list[ContextItemDTO] = []
        with factory() as db_session:
            if context_type in {None, "character", "location", "organization"}:
                statement = select(EntityORM).where(EntityORM.novel_id == self.session.novel.id)
                if context_type:
                    statement = statement.where(EntityORM.entity_type == context_type)
                if status:
                    statement = statement.where(EntityORM.status == status)
                rows.extend(
                    ContextItemDTO(
                        id=item.id,
                        context_type=item.entity_type,
                        source=item.source_name,
                        translation=item.translated_name,
                        description=item.description,
                        status=item.status,
                    )
                    for item in db_session.scalars(statement)
                )
            if context_type in {None, "term"}:
                term_statement = select(TerminologyORM).where(TerminologyORM.novel_id == self.session.novel.id)
                if status:
                    term_statement = term_statement.where(TerminologyORM.status == status)
                rows.extend(
                    ContextItemDTO(
                        id=item.id,
                        context_type="term",
                        source=item.source_term,
                        translation=item.translated_term,
                        description=item.description,
                        status=item.status,
                    )
                    for item in db_session.scalars(term_statement)
                )
        return sorted(rows, key=lambda item: (item.context_type, item.source))

    def list_database_tables(self) -> list[str]:
        """List project-local SQLite tables that can be inspected in the desktop UI."""
        engine = create_sqlite_engine(self.session.settings.database_path)
        try:
            return sorted(inspect(engine).get_table_names())
        finally:
            engine.dispose()

    def get_database_table(self, table_name: str) -> DatabaseTableDTO:
        """Return every cell in one known project table as safe display strings."""
        engine = create_sqlite_engine(self.session.settings.database_path)
        try:
            if table_name not in inspect(engine).get_table_names():
                raise ValueError(f"Unknown database table: {table_name}")
            table = Table(table_name, MetaData(), autoload_with=engine)
            with engine.connect() as connection:
                statement = select(table)
                if table.primary_key.columns:
                    statement = statement.order_by(*table.primary_key.columns)
                result = connection.execute(statement)
                rows = [
                    {column: self._database_display_value(value) for column, value in row._mapping.items()}
                    for row in result
                ]
            return DatabaseTableDTO(name=table_name, columns=[column.name for column in table.columns], rows=rows)
        finally:
            engine.dispose()

    @staticmethod
    def _database_display_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        if isinstance(value, bytes):
            return value.hex()
        return str(value)

    def list_conflicts(self) -> list[ConflictDTO]:
        return [ConflictDTO.model_validate(row) for row in ContextService(self.session).conflicts()]

    def upsert_context(
        self,
        context_type: str,
        source: str,
        translation: str | None,
        description: str | None = None,
        status: str = "confirmed",
    ) -> int:
        return ContextService(self.session).upsert_item(context_type, source, translation, description, status)

    def delete_context(self, context_type: str, source: str) -> None:
        ContextService(self.session).delete_item(context_type, source)

    def resolve_conflict(self, conflict_id: int, action: str, value: str | None = None) -> None:
        ContextService(self.session).resolve(conflict_id, action, value)

    def export_novel(self) -> Path:
        return ExportService(self.session).export()

    def export_context(self) -> Path:
        return ContextService(self.session).export_yaml()
