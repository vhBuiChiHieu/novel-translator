from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_translator.application.services.project_service import ProjectService
from novel_translator.config import ProjectSettings
from novel_translator.domain.context.merger import ContextMerger
from novel_translator.domain.context.retriever import ExactMatchContextRetriever
from novel_translator.domain.model.enums import ChunkStatus, JobStatus
from novel_translator.domain.translation.chunker import ParagraphChapterChunker, normalize_source
from novel_translator.domain.translation.response_validator import validate_response
from novel_translator.infrastructure.model.factory import create_model_provider
from novel_translator.infrastructure.model.provider import ModelProvider
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import (
    ChapterORM,
    NovelORM,
    TranslationChunkORM,
    TranslationJobORM,
)
from novel_translator.infrastructure.persistence.repositories.context_repository import (
    SqlAlchemyContextRepository,
)
from novel_translator.infrastructure.persistence.unit_of_work import SessionFactory
from novel_translator.infrastructure.prompting.jinja_prompt_builder import JinjaPromptBuilder


class ChapterNotFoundError(Exception):
    pass


class SourceChangedError(Exception):
    pass


class TranslationService:
    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def translate(self, chapter_number: int, *, resume: bool = False, force: bool = False) -> TranslationJobORM:
        settings = ProjectService().load_current()
        engine = create_sqlite_engine(settings.database_path)
        sessions = create_session_factory(engine)
        with sessions() as session:
            novel = session.scalar(select(NovelORM).where(NovelORM.project_name == settings.project_name))
            chapter = session.scalar(
                select(ChapterORM).where(ChapterORM.novel_id == novel.id, ChapterORM.chapter_number == chapter_number)
            ) if novel else None
            if novel is None or chapter is None:
                raise ChapterNotFoundError(f"Chapter {chapter_number} was not imported")
            source_path = settings.project_path / chapter.source_path
            source = normalize_source(source_path.read_text(encoding="utf-8"))
            if hashlib.sha256(source.encode("utf-8")).hexdigest() != chapter.source_hash:
                raise SourceChangedError("Source chapter has changed since previous translation.")
            job = self._select_job(session, novel, chapter, settings, resume, force, source)
            job_id = job.id
            session.commit()
        provider = self.provider or create_model_provider(settings.model)
        self._process_job(settings, job_id, provider)
        with sessions() as session:
            completed = session.get(TranslationJobORM, job_id)
            assert completed is not None
            session.expunge(completed)
            return completed

    def _select_job(
        self,
        session: Session,
        novel: NovelORM,
        chapter: ChapterORM,
        settings: ProjectSettings,
        resume: bool,
        force: bool,
        source: str,
    ) -> TranslationJobORM:
        assert hasattr(session, "scalars")
        prior = list(session.scalars(select(TranslationJobORM).where(TranslationJobORM.chapter_id == chapter.id).order_by(TranslationJobORM.id.desc())))
        if resume:
            job = next((item for item in prior if item.status != JobStatus.COMPLETED.value), None)
            if job is not None:
                return job
        if prior and not force and prior[0].status == JobStatus.COMPLETED.value:
            raise ValueError("Chapter already translated; use --force to create a new translation job")
        job = TranslationJobORM(
            novel_id=novel.id,
            chapter_id=chapter.id,
            model_provider=settings.model.provider,
            model_name=settings.model.name,
            prompt_version="translation-v1",
            status=JobStatus.PENDING.value,
        )
        session.add(job)
        session.flush()
        chunker = ParagraphChapterChunker(
            settings.chunk.target_chars, settings.chunk.max_chars, settings.chunk.min_chars
        )
        for chunk in chunker.split(source):
            session.add(
                TranslationChunkORM(
                    translation_job_id=job.id,
                    chapter_id=chapter.id,
                    chunk_index=chunk.index,
                    source_text=chunk.text,
                    status=ChunkStatus.PENDING.value,
                )
            )
        return job

    def _process_job(self, settings: ProjectSettings, job_id: int, provider: ModelProvider) -> None:
        sessions: SessionFactory = create_session_factory(create_sqlite_engine(settings.database_path))
        with sessions() as session:
            job = session.get(TranslationJobORM, job_id)
            assert job is not None
            job.status = JobStatus.RUNNING.value
            job.started_at = job.started_at or datetime.utcnow()
            stale = list(
                session.scalars(
                    select(TranslationChunkORM).where(
                        TranslationChunkORM.translation_job_id == job_id,
                        TranslationChunkORM.status == ChunkStatus.RUNNING.value,
                    )
                )
            )
            for chunk in stale:
                chunk.status = ChunkStatus.FAILED.value
                chunk.error_message = "Interrupted before completion"
            session.commit()
        while True:
            with sessions() as session:
                job = session.get(TranslationJobORM, job_id)
                assert job is not None
                next_chunk = session.scalar(
                    select(TranslationChunkORM)
                    .where(
                        TranslationChunkORM.translation_job_id == job_id,
                        TranslationChunkORM.status != ChunkStatus.COMPLETED.value,
                    )
                    .order_by(TranslationChunkORM.chunk_index)
                )
                if next_chunk is None:
                    break
                tail = self._previous_tail(session, job_id, next_chunk.chunk_index, settings)
                next_chunk.status = ChunkStatus.RUNNING.value
                next_chunk.previous_translation_tail = tail
                session.commit()
                chunk_id, chapter_id, source_text = (
                    next_chunk.id,
                    next_chunk.chapter_id,
                    next_chunk.source_text,
                )
            try:
                self._translate_chunk(settings, sessions, job_id, chunk_id, chapter_id, source_text, tail, provider)
            except Exception as error:
                with sessions() as session:
                    failed = session.get(TranslationChunkORM, chunk_id)
                    assert failed is not None
                    failed.status = ChunkStatus.FAILED.value
                    failed.error_message = str(error)
                    job = session.get(TranslationJobORM, job_id)
                    assert job is not None
                    job.status = JobStatus.PARTIAL.value
                    session.commit()
                raise
        self._assemble_and_complete(settings, sessions, job_id)

    @staticmethod
    def _previous_tail(session: Session, job_id: int, chunk_index: int, settings: ProjectSettings) -> str:
        if not settings.continuity.include_previous_tail:
            return ""
        previous = session.scalar(
            select(TranslationChunkORM)
            .where(TranslationChunkORM.translation_job_id == job_id, TranslationChunkORM.chunk_index == chunk_index - 1)
        )
        if previous is None or not previous.translated_text:
            return ""
        paragraphs = [part for part in previous.translated_text.split("\n\n") if part.strip()]
        return "\n\n".join(paragraphs[-settings.continuity.previous_tail_paragraphs :])

    def _translate_chunk(
        self,
        settings: ProjectSettings,
        sessions: SessionFactory,
        job_id: int,
        chunk_id: int,
        chapter_id: int,
        source_text: str,
        tail: str,
        provider: ModelProvider,
    ) -> None:
        with sessions() as session:
            job = session.get(TranslationJobORM, job_id)
            assert job is not None
            repository = SqlAlchemyContextRepository(session, job.novel_id)
            snapshot = ExactMatchContextRetriever(repository, settings.context).retrieve(source_text)
        rendered = JinjaPromptBuilder().build(settings, source_text, snapshot, tail)
        response = validate_response(provider.translate(rendered.request), source_text, settings.validation)
        with sessions() as session:
            chunk = session.get(TranslationChunkORM, chunk_id)
            job = session.get(TranslationJobORM, job_id)
            assert chunk is not None and job is not None
            repository = SqlAlchemyContextRepository(session, job.novel_id)
            ContextMerger(
                repository, settings.context, source_text, chapter_id, chunk_id, job.model_name, job.prompt_version
            ).merge(response.context_updates)
            chunk.translated_text = response.translation
            chunk.context_snapshot_json = snapshot.model_dump()
            chunk.raw_model_response_json = response.model_dump()
            chunk.prompt_hash = rendered.prompt_hash
            chunk.prompt_tokens = provider.last_metrics.prompt_tokens
            chunk.output_tokens = provider.last_metrics.output_tokens
            chunk.duration_ms = provider.last_metrics.duration_ms
            chunk.status = ChunkStatus.COMPLETED.value
            job.total_prompt_tokens += chunk.prompt_tokens
            job.total_output_tokens += chunk.output_tokens
            job.total_duration_ms += chunk.duration_ms
            session.commit()

    def _assemble_and_complete(
        self, settings: ProjectSettings, sessions: SessionFactory, job_id: int
    ) -> None:
        with sessions() as session:
            job = session.get(TranslationJobORM, job_id)
            assert job is not None
            chunks = list(
                session.scalars(
                    select(TranslationChunkORM)
                    .where(TranslationChunkORM.translation_job_id == job_id)
                    .order_by(TranslationChunkORM.chunk_index)
                )
            )
            if any(chunk.status != ChunkStatus.COMPLETED.value for chunk in chunks):
                raise RuntimeError("Cannot assemble incomplete translation job")
            chapter = session.get(ChapterORM, job.chapter_id)
            assert chapter is not None
            target = settings.project_path / "translated" / f"chapter_{chapter.chapter_number:04d}.txt"
            temporary = target.with_suffix(".txt.tmp")
            temporary.write_text("\n\n".join(chunk.translated_text or "" for chunk in chunks), encoding="utf-8")
            temporary.replace(target)
            chapter.translated_path = str(target.relative_to(settings.project_path))
            chapter.status = "translated"
            job.status = JobStatus.COMPLETED.value
            job.finished_at = datetime.utcnow()
            session.commit()
