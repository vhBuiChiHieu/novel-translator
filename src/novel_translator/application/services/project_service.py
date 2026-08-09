from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy import select

from novel_translator.config import ProjectSettings, default_yaml, load_project_settings
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.migrate import upgrade_database
from novel_translator.infrastructure.persistence.orm.models import NovelORM


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
        upgrade_database(project_path / "data" / "novel.db")
        settings = load_project_settings(project_path)
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
        return project_path

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
        log_path = project_path / "logs" / "novel-translator.log"
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=[logging.FileHandler(log_path, encoding="utf-8")],
            force=True,
        )
