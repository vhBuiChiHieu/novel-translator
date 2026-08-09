from __future__ import annotations

from dataclasses import dataclass

from novel_translator.config import ContextSettings
from novel_translator.domain.context.normalizer import normalize_update
from novel_translator.domain.context.policies import should_auto_confirm
from novel_translator.domain.model.enums import ContextStatus, ContextType, EntityType
from novel_translator.infrastructure.persistence.orm.models import (
    AddressingRuleORM,
    ContextConflictORM,
    ContextFactORM,
    EntityAliasORM,
    EntityORM,
    RelationshipORM,
    TerminologyORM,
)
from novel_translator.infrastructure.persistence.repositories.context_repository import (
    SqlAlchemyContextRepository,
)
from novel_translator.schemas.context_update import ContextUpdate


@dataclass(frozen=True)
class MergeResult:
    inserted: int = 0
    enriched: int = 0
    duplicates: int = 0
    conflicts: int = 0


class ContextMerger:
    def __init__(
        self,
        repository: SqlAlchemyContextRepository,
        settings: ContextSettings,
        source_text: str,
        chapter_id: int | None,
        chunk_id: int | None,
        model_name: str | None,
        prompt_version: str | None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.source_text = source_text
        self.chapter_id = chapter_id
        self.chunk_id = chunk_id
        self.model_name = model_name
        self.prompt_version = prompt_version

    def merge(self, updates: list[ContextUpdate]) -> MergeResult:
        result = MergeResult()
        for raw in updates:
            update = normalize_update(raw)
            if update.type == ContextType.TERM:
                result = self._merge_term(update, result)
            elif update.type in {ContextType.CHARACTER, ContextType.LOCATION, ContextType.ORGANIZATION}:
                result = self._merge_entity(update, result)
            elif update.type == ContextType.RELATIONSHIP:
                result = self._merge_relationship(update, result)
            elif update.type == ContextType.ADDRESSING:
                result = self._merge_addressing(update, result)
            elif update.type == ContextType.WORLD_FACT:
                result = self._merge_fact(update, result)
        return result

    def _status(self, update: ContextUpdate) -> str:
        return (
            ContextStatus.CONFIRMED.value
            if should_auto_confirm(update, self.source_text, self.settings)
            else ContextStatus.CANDIDATE.value
        )

    def _merge_relationship(self, update: ContextUpdate, result: MergeResult) -> MergeResult:
        assert update.subject and update.predicate and update.object
        subject = self.repository.entity_by_any_source(update.subject)
        object_ = self.repository.entity_by_any_source(update.object)
        if subject is None or object_ is None:
            return MergeResult(result.inserted, result.enriched, result.duplicates + 1, result.conflicts)
        existing = self.repository.relationship_by_key(subject.id, update.predicate, object_.id)
        if existing is None:
            self.repository.session.add(
                RelationshipORM(
                    novel_id=self.repository.novel_id,
                    subject_entity_id=subject.id,
                    predicate=update.predicate,
                    object_entity_id=object_.id,
                    description=update.description,
                    status=self._status(update),
                    first_seen_chapter_id=self.chapter_id,
                    first_seen_chunk_id=self.chunk_id,
                    confidence=update.confidence,
                )
            )
            return MergeResult(result.inserted + 1, result.enriched, result.duplicates, result.conflicts)
        if existing.description is None and update.description:
            existing.description = update.description
            return MergeResult(result.inserted, result.enriched + 1, result.duplicates, result.conflicts)
        return MergeResult(result.inserted, result.enriched, result.duplicates + 1, result.conflicts)

    def _merge_addressing(self, update: ContextUpdate, result: MergeResult) -> MergeResult:
        speaker = self.repository.entity_by_any_source(update.speaker) if update.speaker else None
        listener = self.repository.entity_by_any_source(update.listener) if update.listener else None
        self.repository.session.add(
            AddressingRuleORM(
                novel_id=self.repository.novel_id,
                speaker_entity_id=speaker.id if speaker else None,
                listener_entity_id=listener.id if listener else None,
                speaker_pronoun=update.speaker_pronoun,
                listener_pronoun=update.listener_pronoun,
                source_title=update.source_title,
                translated_title=update.translated_title,
                description=update.description,
                status=self._status(update),
                first_seen_chapter_id=self.chapter_id,
                first_seen_chunk_id=self.chunk_id,
            )
        )
        return MergeResult(result.inserted + 1, result.enriched, result.duplicates, result.conflicts)

    def _merge_fact(self, update: ContextUpdate, result: MergeResult) -> MergeResult:
        assert update.subject and update.fact_key and update.fact_value
        existing = self.repository.fact_by_key(update.subject, update.fact_key)
        if existing is None:
            self.repository.session.add(
                ContextFactORM(
                    novel_id=self.repository.novel_id,
                    subject=update.subject,
                    fact_key=update.fact_key,
                    fact_value=update.fact_value,
                    description=update.description,
                    status=self._status(update),
                    first_seen_chapter_id=self.chapter_id,
                    first_seen_chunk_id=self.chunk_id,
                    confidence=update.confidence,
                )
            )
            return MergeResult(result.inserted + 1, result.enriched, result.duplicates, result.conflicts)
        if existing.fact_value != update.fact_value:
            self._conflict(update, existing.fact_value)
            return MergeResult(result.inserted, result.enriched, result.duplicates, result.conflicts + 1)
        if existing.description is None and update.description:
            existing.description = update.description
            return MergeResult(result.inserted, result.enriched + 1, result.duplicates, result.conflicts)
        return MergeResult(result.inserted, result.enriched, result.duplicates + 1, result.conflicts)

    def _merge_entity(self, update: ContextUpdate, result: MergeResult) -> MergeResult:
        assert update.source is not None
        existing = self.repository.entity_by_source(update.source, EntityType(update.type.value))
        if existing is None:
            status = (
                ContextStatus.CONFIRMED.value
                if should_auto_confirm(update, self.source_text, self.settings)
                else ContextStatus.CANDIDATE.value
            )
            entity = EntityORM(
                novel_id=self.repository.novel_id,
                entity_type=update.type.value,
                source_name=update.source,
                translated_name=update.translation,
                description=update.description,
                status=status,
                first_seen_chapter_id=self.chapter_id,
                first_seen_chunk_id=self.chunk_id,
                created_by_model=self.model_name,
                prompt_version=self.prompt_version,
            )
            self.repository.session.add(entity)
            self.repository.session.flush()
            for alias in update.aliases:
                self.repository.session.add(EntityAliasORM(entity_id=entity.id, alias=alias, alias_type="source_alias"))
            return MergeResult(result.inserted + 1, result.enriched, result.duplicates, result.conflicts)
        if existing.translated_name and update.translation and existing.translated_name != update.translation:
            self._conflict(update, existing.translated_name)
            return MergeResult(result.inserted, result.enriched, result.duplicates, result.conflicts + 1)
        changed = False
        if existing.translated_name is None and update.translation:
            existing.translated_name = update.translation
            changed = True
        if existing.description is None and update.description:
            existing.description = update.description
            changed = True
        if changed:
            return MergeResult(result.inserted, result.enriched + 1, result.duplicates, result.conflicts)
        return MergeResult(result.inserted, result.enriched, result.duplicates + 1, result.conflicts)

    def _merge_term(self, update: ContextUpdate, result: MergeResult) -> MergeResult:
        assert update.source is not None
        existing = self.repository.term_by_source(update.source)
        if existing is None:
            status = (
                ContextStatus.CONFIRMED.value
                if should_auto_confirm(update, self.source_text, self.settings)
                else ContextStatus.CANDIDATE.value
            )
            self.repository.session.add(
                TerminologyORM(
                    novel_id=self.repository.novel_id,
                    source_term=update.source,
                    translated_term=update.translation,
                    description=update.description,
                    status=status,
                    first_seen_chapter_id=self.chapter_id,
                    first_seen_chunk_id=self.chunk_id,
                    created_by_model=self.model_name,
                    prompt_version=self.prompt_version,
                )
            )
            return MergeResult(result.inserted + 1, result.enriched, result.duplicates, result.conflicts)
        if existing.translated_term and update.translation and existing.translated_term != update.translation:
            self._conflict(update, existing.translated_term)
            return MergeResult(result.inserted, result.enriched, result.duplicates, result.conflicts + 1)
        changed = False
        if existing.translated_term is None and update.translation:
            existing.translated_term = update.translation
            changed = True
        if existing.description is None and update.description:
            existing.description = update.description
            changed = True
        if changed:
            return MergeResult(result.inserted, result.enriched + 1, result.duplicates, result.conflicts)
        return MergeResult(result.inserted, result.enriched, result.duplicates + 1, result.conflicts)

    def _conflict(self, update: ContextUpdate, existing_value: str) -> None:
        self.repository.add_conflict(
            ContextConflictORM(
                novel_id=self.repository.novel_id,
                context_type=update.type.value,
                source_key=update.source or "",
                existing_value=existing_value,
                candidate_value=update.translation,
                chapter_id=self.chapter_id,
                chunk_id=self.chunk_id,
                status="open",
            )
        )
