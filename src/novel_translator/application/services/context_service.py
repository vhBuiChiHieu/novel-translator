from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import select

from novel_translator.application.services.project_service import ProjectService
from novel_translator.domain.model.enums import ContextStatus, ContextType
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import (
    ContextConflictORM,
    EntityORM,
    TerminologyORM,
)


class ContextService:
    def _session_and_novel(self):
        settings = ProjectService().load_current()
        sessions = create_session_factory(create_sqlite_engine(settings.database_path))
        novel = ProjectService().get_novel(settings)
        return settings, sessions, novel

    def list_items(self, context_type: str | None, status: str | None) -> list[tuple[str, str, str | None, str]]:
        _, sessions, novel = self._session_and_novel()
        rows: list[tuple[str, str, str | None, str]] = []
        with sessions() as session:
            if context_type in {None, "character", "location", "organization"}:
                statement = select(EntityORM).where(EntityORM.novel_id == novel.id)
                if context_type:
                    statement = statement.where(EntityORM.entity_type == context_type)
                if status:
                    statement = statement.where(EntityORM.status == status)
                rows.extend((entity.entity_type, entity.source_name, entity.translated_name, entity.status) for entity in session.scalars(statement))
            if context_type in {None, "term"}:
                term_statement = select(TerminologyORM).where(TerminologyORM.novel_id == novel.id)
                if status:
                    term_statement = term_statement.where(TerminologyORM.status == status)
                rows.extend(
                    ("term", term.source_term, term.translated_term, term.status)
                    for term in session.scalars(term_statement)
                )
        return sorted(rows)

    def import_yaml(self, path: Path) -> int:
        settings, sessions, novel = self._session_and_novel()
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        count = 0
        with sessions() as session:
            for type_name, entity_type in (("characters", "character"), ("locations", "location"), ("organizations", "organization")):
                for item in data.get(type_name, []):
                    source, translation = item["source"], item.get("translation")
                    existing = session.scalar(select(EntityORM).where(EntityORM.novel_id == novel.id, EntityORM.entity_type == entity_type, EntityORM.source_name == source))
                    if existing is None:
                        session.add(EntityORM(novel_id=novel.id, entity_type=entity_type, source_name=source, translated_name=translation, description=item.get("description"), status=ContextStatus.CONFIRMED.value, prompt_version="manual_import"))
                        count += 1
            for item in data.get("terms", []):
                source, translation = item["source"], item.get("translation")
                existing = session.scalar(select(TerminologyORM).where(TerminologyORM.novel_id == novel.id, TerminologyORM.source_term == source))
                if existing is None:
                    session.add(TerminologyORM(novel_id=novel.id, source_term=source, translated_term=translation, description=item.get("description"), status=ContextStatus.CONFIRMED.value, prompt_version="manual_import"))
                    count += 1
            session.commit()
        return count

    def export_yaml(self) -> Path:
        settings, sessions, novel = self._session_and_novel()
        result: dict[str, list[dict[str, str | None]]] = {"characters": [], "locations": [], "organizations": [], "terms": []}
        with sessions() as session:
            for entity in session.scalars(select(EntityORM).where(EntityORM.novel_id == novel.id).order_by(EntityORM.source_name)):
                result[f"{entity.entity_type}s"].append({"source": entity.source_name, "translation": entity.translated_name, "description": entity.description})
            for term in session.scalars(select(TerminologyORM).where(TerminologyORM.novel_id == novel.id).order_by(TerminologyORM.source_term)):
                result["terms"].append({"source": term.source_term, "translation": term.translated_term, "description": term.description})
        output = settings.project_path / "exports" / "context.yaml"
        with output.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(result, stream, allow_unicode=True, sort_keys=False)
        return output

    def conflicts(self) -> list[ContextConflictORM]:
        _, sessions, novel = self._session_and_novel()
        with sessions() as session:
            rows = list(session.scalars(select(ContextConflictORM).where(ContextConflictORM.novel_id == novel.id).order_by(ContextConflictORM.id)))
            for row in rows:
                session.expunge(row)
            return rows

    def resolve(self, conflict_id: int, action: str, value: str | None = None) -> None:
        _, sessions, novel = self._session_and_novel()
        with sessions() as session:
            conflict = session.scalar(select(ContextConflictORM).where(ContextConflictORM.id == conflict_id, ContextConflictORM.novel_id == novel.id))
            if conflict is None or conflict.status != "open":
                raise ValueError(f"Open conflict {conflict_id} was not found")
            if action == "existing":
                conflict.status = "accept_existing"
            else:
                candidate = value if action == "custom" else conflict.candidate_value
                if conflict.context_type == ContextType.TERM.value:
                    item = session.scalar(select(TerminologyORM).where(TerminologyORM.novel_id == novel.id, TerminologyORM.source_term == conflict.source_key))
                    if item:
                        item.translated_term = candidate
                else:
                    item = session.scalar(select(EntityORM).where(EntityORM.novel_id == novel.id, EntityORM.entity_type == conflict.context_type, EntityORM.source_name == conflict.source_key))
                    if item:
                        item.translated_name = candidate
                conflict.status = "custom" if action == "custom" else "accept_candidate"
            conflict.resolved_at = datetime.utcnow()
            session.commit()
