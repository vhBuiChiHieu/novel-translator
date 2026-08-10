from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.config import ProjectSettings, load_project_settings
from novel_translator.infrastructure.persistence.database import create_session_factory, create_sqlite_engine
from novel_translator.infrastructure.persistence.orm.models import NovelORM


class ConfigService:
    """Validated YAML configuration editor with optional Windows credential storage."""

    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = open_project_session(session, project_path)

    def load(self) -> ProjectSettings:
        return load_project_settings(self.session.project_path)

    def update(self, updates: dict[str, Any]) -> ProjectSettings:
        current = self.load()
        data = current.model_dump(exclude={"project_path"}, mode="python")
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
        data["project_path"] = self.session.project_path
        updated = ProjectSettings.model_validate(data)
        self._write_yaml(updated)
        self._sync_novel(updated)
        self.session = ProjectSession(
            project_path=self.session.project_path,
            settings=updated,
            novel=self.session.novel.model_copy(
                update={
                    "title": updated.title,
                    "source_language": updated.source_language,
                    "target_language": updated.target_language,
                }
            ),
        )
        return updated

    def update_settings(self, updates: dict[str, Any]) -> ProjectSettings:
        return self.update(updates)

    def set_api_key(self, api_key: str) -> None:
        if not api_key:
            self.clear_api_key()
            return
        try:
            import keyring

            keyring.set_password("novel-translator", self.session.settings.project_name, api_key)
        except ImportError as error:
            raise RuntimeError("Credential storage requires the desktop/keyring extra") from error
        # ProjectSession is immutable by design. Reload it so the UI and any
        # subsequent worker see the credential immediately instead of waiting
        # for the next application restart.
        self.session = ProjectSession.open(self.session.project_path)

    def clear_api_key(self) -> None:
        try:
            import keyring
        except ImportError:
            return
        try:
            keyring.delete_password("novel-translator", self.session.settings.project_name)
        except Exception:
            pass
        self.session = ProjectSession.open(self.session.project_path)

    def _write_yaml(self, settings: ProjectSettings) -> None:
        context = settings.context.model_dump()
        context["minimum_confidence"] = {"auto_confirm": context.pop("minimum_confidence")}
        data = {
            "project": {"name": settings.project_name},
            "novel": {
                "title": settings.title,
                "source_language": settings.source_language,
                "target_language": settings.target_language,
            },
            "genre": settings.genre,
            "model": settings.model.model_dump(exclude_none=True),
            "translation": {
                "prompt_version": settings.prompt_version,
                "chunk": settings.chunk.model_dump(),
                "continuity": settings.continuity.model_dump(),
            },
            "context": context,
            "validation": settings.validation.model_dump(),
            "log_level": settings.log_level,
        }
        with (self.session.project_path / "novel.yaml").open("w", encoding="utf-8") as stream:
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)

    def _sync_novel(self, settings: ProjectSettings) -> None:
        factory = create_session_factory(create_sqlite_engine(settings.database_path))
        with factory() as db_session:
            novel = db_session.get(NovelORM, self.session.novel.id)
            if novel is not None:
                novel.title = settings.title
                novel.source_language = settings.source_language
                novel.target_language = settings.target_language
            db_session.commit()
