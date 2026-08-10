from __future__ import annotations

from pathlib import Path

from novel_translator.application.session import ProjectSession


def open_project_session(
    session: ProjectSession | None = None, project_path: Path | None = None
) -> ProjectSession:
    if session is not None:
        return session
    return ProjectSession.open((project_path or Path.cwd()).resolve())
