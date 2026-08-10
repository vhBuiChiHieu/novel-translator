from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from novel_translator.config import ProjectSettings

from .dtos import NovelDTO


@dataclass(frozen=True)
class ProjectSession:
    """Immutable context for one explicitly opened Novel Translator project."""

    project_path: Path
    settings: ProjectSettings
    novel: NovelDTO

    @classmethod
    def open(cls, project_path: Path) -> ProjectSession:
        # Imported lazily to keep ProjectService independent from this value object.
        from novel_translator.application.services.project_service import ProjectService

        return ProjectService().open_session(project_path)
