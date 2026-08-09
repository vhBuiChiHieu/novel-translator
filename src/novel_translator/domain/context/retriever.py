from __future__ import annotations

from novel_translator.config import ContextSettings
from novel_translator.infrastructure.persistence.orm.models import EntityORM
from novel_translator.infrastructure.persistence.repositories.context_repository import (
    SqlAlchemyContextRepository,
)
from novel_translator.schemas.context_snapshot import (
    AddressingContext,
    ContextItem,
    ContextSnapshot,
    RelationshipContext,
    WorldFactContext,
)


class ExactMatchContextRetriever:
    def __init__(self, repository: SqlAlchemyContextRepository, settings: ContextSettings) -> None:
        self.repository = repository
        self.settings = settings

    def retrieve(self, source_text: str) -> ContextSnapshot:
        direct: dict[int, EntityORM] = {}
        aliases: dict[int, list[str]] = {}
        for entity in self.repository.confirmed_entities():
            known_aliases = [row.alias for row in self.repository.aliases_for(entity.id)]
            aliases[entity.id] = known_aliases
            if entity.source_name in source_text or any(alias in source_text for alias in known_aliases):
                direct[entity.id] = entity
        expanded: dict[int, EntityORM] = {}
        relationships = []
        all_entities = {entity.id: entity for entity in self.repository.confirmed_entities()}
        for relation in self.repository.confirmed_relationships():
            if relation.subject_entity_id in direct or relation.object_entity_id in direct:
                relationships.append(relation)
                related_id = (
                    relation.object_entity_id
                    if relation.subject_entity_id in direct
                    else relation.subject_entity_id
                )
                if related_id not in direct:
                    expanded[related_id] = all_entities[related_id]
        ordered_entities = sorted(
            [*direct.values(), *expanded.values()], key=lambda entity: (entity.id not in direct, entity.source_name)
        )[: self.settings.max_characters_per_request]
        entity_ids = {entity.id for entity in ordered_entities}
        entity_items = [
            ContextItem(
                source=entity.source_name,
                translation=entity.translated_name,
                description=entity.description,
                aliases=aliases.get(entity.id, []),
            )
            for entity in ordered_entities
        ]
        grouped: dict[str, list[ContextItem]] = {
            "character": [],
            "location": [],
            "organization": [],
        }
        for entity, item in zip(ordered_entities, entity_items, strict=True):
            grouped[entity.entity_type].append(item)
        terms = sorted(
            [
                ContextItem(source=term.source_term, translation=term.translated_term, description=term.description)
                for term in self.repository.confirmed_terms()
                if term.source_term in source_text
            ],
            key=lambda item: (-len(item.source), item.source),
        )[: self.settings.max_terms_per_request]
        relation_items = []
        for relation in relationships:
            subject = all_entities[relation.subject_entity_id].source_name
            object_ = all_entities[relation.object_entity_id].source_name
            relation_items.append(
                RelationshipContext(
                    subject=subject, predicate=relation.predicate, object=object_, description=relation.description
                )
            )
        relation_items.sort(key=lambda item: (item.subject, item.predicate, item.object))
        addressing = []
        for rule in self.repository.confirmed_addressing():
            if rule.speaker_entity_id in entity_ids or rule.listener_entity_id in entity_ids:
                addressing.append(
                    AddressingContext(
                        speaker=all_entities[rule.speaker_entity_id].source_name
                        if rule.speaker_entity_id else None,
                        listener=all_entities[rule.listener_entity_id].source_name
                        if rule.listener_entity_id else None,
                        speaker_pronoun=rule.speaker_pronoun,
                        listener_pronoun=rule.listener_pronoun,
                        source_title=rule.source_title,
                        translated_title=rule.translated_title,
                    )
                )
        facts = [
            WorldFactContext(
                subject=fact.subject,
                fact_key=fact.fact_key,
                fact_value=fact.fact_value,
                description=fact.description,
            )
            for fact in self.repository.confirmed_facts()
            if fact.subject in source_text
        ][: self.settings.max_facts_per_request]
        return ContextSnapshot(
            characters=grouped["character"],
            locations=grouped["location"],
            organizations=grouped["organization"],
            terms=terms,
            relationships=relation_items[: self.settings.max_relationships_per_request],
            addressing_rules=sorted(addressing, key=lambda item: (item.speaker or "", item.listener or "")),
            world_facts=facts,
        )
