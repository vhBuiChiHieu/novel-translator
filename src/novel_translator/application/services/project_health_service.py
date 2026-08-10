from __future__ import annotations

from pathlib import Path

from novel_translator.application.project_scope import open_project_session
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.session import ProjectSession


class ProjectHealthService:
    def check(self, project_path: Path) -> list[str]:
        return ProjectService().validate(project_path)

    def check_open_project(self, session: ProjectSession | None = None, project_path: Path | None = None) -> list[str]:
        active = open_project_session(session, project_path)
        return self.check(active.project_path)
