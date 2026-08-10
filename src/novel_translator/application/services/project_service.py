from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from sqlalchemy import select

from novel_translator.config import ProjectSettings, default_yaml, load_project_settings
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.migrate import upgrade_database
from novel_translator.infrastructure.persistence.orm.models import NovelORM
from novel_translator.infrastructure.project_logging import configure_project_logging

if TYPE_CHECKING:
    from novel_translator.application.session import ProjectSession


class ProjectNotFoundError(Exception):
    pass


class ProjectService:
    def init(self, parent: Path, name: str) -> Path:
        project_path = parent / name
        if project_path.exists():
            raise FileExistsError(f"Project already exists: {project_path}")
        project_path.mkdir()
        for directory in ("data", "source", "translated", "exports", "logs"):
            (project_path / directory).mkdir()
        with (project_path / "novel.yaml").open("w", encoding="utf-8") as stream:
            yaml.safe_dump(default_yaml(name), stream, allow_unicode=True, sort_keys=False)
        self._configure_logging(project_path, "INFO")
        settings = load_project_settings(project_path)
        self._create_database(settings)
        return project_path

    def reset(self, path: Path) -> ProjectSettings:
        """Clear imported and generated novel data while preserving ``novel.yaml``."""
        project_path = path.expanduser().resolve()
        settings = self.load_current(project_path)
        for directory in ("data", "source", "translated", "exports"):
            target = project_path / directory
            if target.exists():
                shutil.rmtree(target)
            target.mkdir()
        self._create_database(settings)
        return settings

    @staticmethod
    def _create_database(settings: ProjectSettings) -> None:
        upgrade_database(settings.database_path)
        engine = create_sqlite_engine(settings.database_path)
        with create_session_factory(engine)() as session:
            session.add(
                NovelORM(
                    project_name=settings.project_name,
                    title=settings.title,
                    source_language=settings.source_language,
                    target_language=settings.target_language,
                )
            )
            session.commit()

    def load_current(self, path: Path | None = None) -> ProjectSettings:
        project_path = (path or Path.cwd()).resolve()
        try:
            settings = load_project_settings(project_path)
        except FileNotFoundError as error:
            raise ProjectNotFoundError(
                "Current directory is not a novel project. Run this command inside a directory containing novel.yaml."
            ) from error
        self._configure_logging(project_path, settings.log_level)
        return settings

    def open_session(self, path: Path) -> ProjectSession:
        """Open a project from any directory and run pending database migrations."""
        project_path = path.expanduser().resolve()
        settings = self.load_current(project_path)
        if not settings.database_path.exists():
            raise ProjectNotFoundError(
                f"Project database is missing: {settings.database_path}. The project must be initialized first."
            )
        try:
            upgrade_database(settings.database_path)
            novel = self.get_novel(settings)
        except Exception as error:
            raise ProjectNotFoundError(f"Project database is invalid: {error}") from error
        from novel_translator.application.dtos import NovelDTO
        from novel_translator.application.session import ProjectSession

        return ProjectSession(project_path=project_path, settings=settings, novel=NovelDTO.model_validate(novel))

    def validate(self, path: Path) -> list[str]:
        """Return human-readable project validation errors without mutating the project."""
        project_path = path.expanduser().resolve()
        errors: list[str] = []
        if not (project_path / "novel.yaml").is_file():
            errors.append("novel.yaml is missing")
        if not (project_path / "data" / "novel.db").is_file():
            errors.append("data/novel.db is missing")
        for directory in ("source", "translated", "exports", "logs"):
            if not (project_path / directory).is_dir():
                errors.append(f"{directory}/ directory is missing")
        if errors:
            return errors
        try:
            settings = load_project_settings(project_path)
            self.get_novel(settings)
        except Exception as error:
            errors.append(str(error))
        return errors

    def get_novel(self, settings: ProjectSettings) -> NovelORM:
        engine = create_sqlite_engine(settings.database_path)
        with create_session_factory(engine)() as session:
            novel = session.scalar(select(NovelORM).where(NovelORM.project_name == settings.project_name))
            if novel is None:
                raise RuntimeError("Project database has no novel record")
            session.expunge(novel)
            return novel

    @staticmethod
    def _configure_logging(project_path: Path, level: str) -> None:
        configure_project_logging(project_path, level)
