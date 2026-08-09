from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_translator.domain.model.enums import ContextStatus, EntityType
from novel_translator.infrastructure.persistence.orm.models import (
    AddressingRuleORM,
    ContextConflictORM,
    ContextFactORM,
    EntityAliasORM,
    EntityORM,
    RelationshipORM,
    TerminologyORM,
)


class SqlAlchemyContextRepository:
    def __init__(self, session: Session, novel_id: int) -> None:
        self.session = session
        self.novel_id = novel_id

    def confirmed_entities(self) -> list[EntityORM]:
        return list(
            self.session.scalars(
                select(EntityORM).where(
                    EntityORM.novel_id == self.novel_id,
                    EntityORM.status == ContextStatus.CONFIRMED.value,
                )
            )
        )

    def aliases_for(self, entity_id: int) -> list[EntityAliasORM]:
        return list(self.session.scalars(select(EntityAliasORM).where(EntityAliasORM.entity_id == entity_id)))

    def confirmed_terms(self) -> list[TerminologyORM]:
        return list(
            self.session.scalars(
                select(TerminologyORM).where(
                    TerminologyORM.novel_id == self.novel_id,
                    TerminologyORM.status == ContextStatus.CONFIRMED.value,
                )
            )
        )

    def confirmed_relationships(self) -> list[RelationshipORM]:
        return list(
            self.session.scalars(
                select(RelationshipORM).where(
                    RelationshipORM.novel_id == self.novel_id,
                    RelationshipORM.status == ContextStatus.CONFIRMED.value,
                )
            )
        )

    def confirmed_addressing(self) -> list[AddressingRuleORM]:
        return list(
            self.session.scalars(
                select(AddressingRuleORM).where(
                    AddressingRuleORM.novel_id == self.novel_id,
                    AddressingRuleORM.status == ContextStatus.CONFIRMED.value,
                )
            )
        )

    def confirmed_facts(self) -> list[ContextFactORM]:
        return list(
            self.session.scalars(
                select(ContextFactORM).where(
                    ContextFactORM.novel_id == self.novel_id,
                    ContextFactORM.status == ContextStatus.CONFIRMED.value,
                )
            )
        )

    def entity_by_source(self, source: str, entity_type: EntityType) -> EntityORM | None:
        return self.session.scalar(
            select(EntityORM).where(
                EntityORM.novel_id == self.novel_id,
                EntityORM.entity_type == entity_type.value,
                EntityORM.source_name == source,
            )
        )

    def term_by_source(self, source: str) -> TerminologyORM | None:
        return self.session.scalar(
            select(TerminologyORM).where(
                TerminologyORM.novel_id == self.novel_id, TerminologyORM.source_term == source
            )
        )

    def entity_by_any_source(self, source: str) -> EntityORM | None:
        return self.session.scalar(
            select(EntityORM).where(EntityORM.novel_id == self.novel_id, EntityORM.source_name == source)
        )

    def relationship_by_key(
        self, subject_id: int, predicate: str, object_id: int
    ) -> RelationshipORM | None:
        return self.session.scalar(
            select(RelationshipORM).where(
                RelationshipORM.novel_id == self.novel_id,
                RelationshipORM.subject_entity_id == subject_id,
                RelationshipORM.predicate == predicate,
                RelationshipORM.object_entity_id == object_id,
            )
        )

    def fact_by_key(self, subject: str, fact_key: str) -> ContextFactORM | None:
        return self.session.scalar(
            select(ContextFactORM).where(
                ContextFactORM.novel_id == self.novel_id,
                ContextFactORM.subject == subject,
                ContextFactORM.fact_key == fact_key,
            )
        )

    def add_conflict(self, conflict: ContextConflictORM) -> None:
        self.session.add(conflict)
