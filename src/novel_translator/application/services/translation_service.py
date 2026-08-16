from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.config import ProjectSettings
from novel_translator.domain.context.merger import ContextMerger
from novel_translator.domain.context.retriever import ExactMatchContextRetriever
from novel_translator.domain.model.enums import ChunkStatus, JobStatus
from novel_translator.domain.translation.chunker import ParagraphChapterChunker, normalize_source
from novel_translator.domain.translation.response_validator import validate_response
from novel_translator.infrastructure.model.factory import create_model_provider
from novel_translator.infrastructure.model.provider import ModelProvider, ProviderAttempt, ProviderMetrics
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import (
    ChapterORM,
    ModelCallORM,
    NovelORM,
    TranslationChunkORM,
    TranslationJobORM,
)
from novel_translator.infrastructure.persistence.repositories.context_repository import (
    SqlAlchemyContextRepository,
)
from novel_translator.infrastructure.persistence.unit_of_work import SessionFactory
from novel_translator.infrastructure.prompting.jinja_prompt_builder import JinjaPromptBuilder
from novel_translator.schemas.translation_response import TranslationResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranslationProgress:
    event: str
    chapter_number: int
    chunk_index: int | None = None
    total_chunks: int | None = None
    duration_ms: int | None = None
    error: str | None = None


class ChapterNotFoundError(Exception):
    pass


class SourceChangedError(Exception):
    pass


class TranslationCancelledError(Exception):
    """Raised when a queued translation is stopped at a chunk boundary."""


class TranslationService:
    def __init__(
        self,
        provider: ModelProvider | None = None,
        session: ProjectSession | None = None,
        project_path: Path | None = None,
    ) -> None:
        self.provider = provider
        self.session = session
        self.project_path = project_path

    def translate(
        self,
        chapter_number: int,
        *,
        resume: bool = False,
        force: bool = False,
        on_progress: Callable[[TranslationProgress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranslationJobORM:
        active = open_project_session(self.session, self.project_path)
        settings = active.settings
        engine = create_sqlite_engine(settings.database_path)
        sessions = create_session_factory(engine)
        with sessions() as session:
            chapter = session.scalar(
                select(ChapterORM).where(ChapterORM.novel_id == active.novel.id, ChapterORM.chapter_number == chapter_number)
            )
            if chapter is None:
                raise ChapterNotFoundError(f"Chapter {chapter_number} was not imported")
            source_path = settings.project_path / chapter.source_path
            source = normalize_source(source_path.read_text(encoding="utf-8"))
            if hashlib.sha256(source.encode("utf-8")).hexdigest() != chapter.source_hash:
                raise SourceChangedError("Source chapter has changed since previous translation.")
            novel = session.get(NovelORM, active.novel.id)
            assert novel is not None
            provider = self.provider or create_model_provider(settings.model)
            profile_id = getattr(provider, "profile_id", None)
            config_hash = getattr(provider, "config_hash", None) or self._legacy_config_hash(settings)
            job = self._select_job(
                session,
                novel,
                chapter,
                settings,
                resume,
                force,
                source,
                profile_id,
                config_hash,
                provider,
            )
            job_id = job.id
            session.commit()
        self._process_job(settings, job_id, chapter_number, provider, on_progress, should_cancel)
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
        profile_id: str | None,
        config_hash: str,
        provider: ModelProvider,
    ) -> TranslationJobORM:
        assert hasattr(session, "scalars")
        prior = list(session.scalars(select(TranslationJobORM).where(TranslationJobORM.chapter_id == chapter.id).order_by(TranslationJobORM.id.desc())))
        if resume:
            job = next((item for item in prior if item.status != JobStatus.COMPLETED.value), None)
            if job is not None:
                if self._job_provider_changed(job, settings, profile_id, config_hash) and not force:
                    raise ValueError("The active provider differs from the provider used by this job; use force to resume")
                if force:
                    job.model_provider = self._provider_name(provider, settings)
                    job.model_name = self._model_name(provider, settings)
                    job.profile_id = profile_id
                    job.config_hash = config_hash
                return job
        if not resume and any(item.status == JobStatus.RUNNING.value for item in prior):
            raise ValueError("A translation job is already running for this chapter")
        if prior and not force and prior[0].status == JobStatus.COMPLETED.value:
            raise ValueError("Chapter already translated; use --force to create a new translation job")
        job = TranslationJobORM(
            novel_id=novel.id,
            chapter_id=chapter.id,
            model_provider=settings.model.provider,
            model_name=settings.model.name,
            profile_id=profile_id,
            config_hash=config_hash,
            prompt_version=settings.prompt_version,
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

    @staticmethod
    def _provider_name(provider: ModelProvider, settings: ProjectSettings) -> str:
        configured = getattr(provider, "settings", None)
        value = getattr(configured, "provider", settings.model.provider)
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _model_name(provider: ModelProvider, settings: ProjectSettings) -> str:
        configured = getattr(provider, "settings", None)
        return str(getattr(configured, "model", None) or getattr(configured, "name", settings.model.name))

    @classmethod
    def _job_provider_changed(
        cls, job: TranslationJobORM, settings: ProjectSettings, profile_id: str | None, config_hash: str
    ) -> bool:
        return (
            (job.profile_id is not None and job.profile_id != profile_id)
            or (job.config_hash is not None and job.config_hash != config_hash)
            or job.model_provider != settings.model.provider
            or job.model_name != settings.model.name
        )

    @staticmethod
    def _legacy_config_hash(settings: ProjectSettings) -> str:
        payload = settings.model.model_dump(exclude={"api_key"}, mode="json")
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _process_job(
        self,
        settings: ProjectSettings,
        job_id: int,
        chapter_number: int,
        provider: ModelProvider,
        on_progress: Callable[[TranslationProgress], None] | None,
        should_cancel: Callable[[], bool] | None,
    ) -> None:
        sessions: SessionFactory = create_session_factory(create_sqlite_engine(settings.database_path))
        with sessions() as session:
            job = session.get(TranslationJobORM, job_id)
            assert job is not None
            job.status = JobStatus.RUNNING.value
            job.started_at = job.started_at or datetime.utcnow()
            total_chunks = len(
                list(
                    session.scalars(
                        select(TranslationChunkORM).where(TranslationChunkORM.translation_job_id == job_id)
                    )
                )
            )
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
        self._emit_progress(on_progress, TranslationProgress("job_started", chapter_number, total_chunks=total_chunks))
        logger.info("Translation started job_id=%s chapter=%s chunks=%s", job_id, chapter_number, total_chunks)
        while True:
            with sessions() as session:
                job = session.get(TranslationJobORM, job_id)
                assert job is not None
                if should_cancel is not None and should_cancel():
                    job.status = JobStatus.PARTIAL.value
                    session.commit()
                    raise TranslationCancelledError("Stopping after current chunk")
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
                chunk_id, chapter_id, source_text, chunk_index = (
                    next_chunk.id,
                    next_chunk.chapter_id,
                    next_chunk.source_text,
                    next_chunk.chunk_index,
                )
            self._emit_progress(
                on_progress,
                TranslationProgress("chunk_started", chapter_number, chunk_index, total_chunks),
            )
            logger.info("Translation chunk started job_id=%s chunk=%s/%s", job_id, chunk_index + 1, total_chunks)
            try:
                self._translate_chunk(settings, sessions, job_id, chunk_id, chapter_id, source_text, tail, provider)
            except Exception as error:
                with sessions() as session:
                    failed = session.get(TranslationChunkORM, chunk_id)
                    assert failed is not None
                    failed.status = ChunkStatus.FAILED.value
                    failed.error_message = str(error)
                    diagnostic = getattr(provider, "last_diagnostic", None)
                    if diagnostic is not None:
                        failed.raw_model_response_json = diagnostic.model_dump()
                    job = session.get(TranslationJobORM, job_id)
                    assert job is not None
                    job.status = JobStatus.PARTIAL.value
                    session.commit()
                logger.exception("Translation chunk failed job_id=%s chunk=%s/%s", job_id, chunk_index + 1, total_chunks)
                self._emit_progress(
                    on_progress,
                    TranslationProgress("chunk_failed", chapter_number, chunk_index, total_chunks, error=str(error)),
                )
                raise
            self._emit_progress(
                on_progress,
                TranslationProgress(
                    "chunk_completed", chapter_number, chunk_index, total_chunks, provider.last_metrics.duration_ms
                ),
            )
            logger.info("Translation chunk completed job_id=%s chunk=%s/%s", job_id, chunk_index + 1, total_chunks)
        self._assemble_and_complete(settings, sessions, job_id)
        self._emit_progress(on_progress, TranslationProgress("job_completed", chapter_number, total_chunks=total_chunks))
        logger.info("Translation completed job_id=%s chapter=%s", job_id, chapter_number)

    @staticmethod
    def _emit_progress(
        callback: Callable[[TranslationProgress], None] | None, event: TranslationProgress
    ) -> None:
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            logger.warning("Translation progress callback failed", exc_info=True)

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
            rendered = JinjaPromptBuilder(job.prompt_version).build(settings, source_text, snapshot, tail)
            previous_attempt = session.scalar(
                select(func.max(ModelCallORM.attempt_number)).where(
                    ModelCallORM.translation_job_id == job_id,
                    ModelCallORM.translation_chunk_id == chunk_id,
                )
            )
            audit = ModelCallORM(
                translation_job_id=job_id,
                translation_chunk_id=chunk_id,
                attempt_number=(previous_attempt or 0) + 1,
                provider=job.model_provider,
                model_name=job.model_name,
                prompt_version=job.prompt_version,
                system_prompt=rendered.request.system_prompt,
                user_prompt=rendered.request.user_prompt,
                source_text=source_text,
                context_snapshot_json=snapshot.model_dump(),
                previous_translation_tail=tail,
                prompt_hash=rendered.prompt_hash,
                status="running",
            )
            session.add(audit)
            session.flush()
            audit_id = audit.id
            session.commit()
        try:
            response = validate_response(provider.translate(rendered.request), source_text, settings.validation)
        except Exception:
            with sessions() as session:
                audit_row = session.get(ModelCallORM, audit_id)
                if audit_row is not None:
                    self._persist_model_call_attempts(session, audit_row, provider, None, "failed")
                    session.commit()
            raise
        with sessions() as session:
            chunk = session.get(TranslationChunkORM, chunk_id)
            job = session.get(TranslationJobORM, job_id)
            audit_row = session.get(ModelCallORM, audit_id)
            assert chunk is not None and job is not None and audit_row is not None
            repository = SqlAlchemyContextRepository(session, job.novel_id)
            ContextMerger(
                repository, settings.context, source_text, chapter_id, chunk_id, job.model_name, job.prompt_version
            ).merge(response.context_updates)
            chunk.translated_text = response.translation
            chunk.context_snapshot_json = snapshot.model_dump()
            chunk.raw_model_response_json = response.model_dump(exclude_none=True)
            chunk.prompt_hash = rendered.prompt_hash
            chunk.prompt_tokens = provider.last_metrics.prompt_tokens
            chunk.output_tokens = provider.last_metrics.output_tokens
            chunk.duration_ms = provider.last_metrics.duration_ms
            chunk.status = ChunkStatus.COMPLETED.value
            self._persist_model_call_attempts(session, audit_row, provider, response, "completed")
            job.total_prompt_tokens += chunk.prompt_tokens
            job.total_output_tokens += chunk.output_tokens
            job.total_duration_ms += chunk.duration_ms
            session.commit()

    @staticmethod
    def _persist_model_call_attempts(
        session: Session,
        first_call: ModelCallORM,
        provider: ModelProvider,
        response: TranslationResponse | None,
        default_status: str,
    ) -> None:
        attempts = getattr(provider, "last_attempts", None) or [
            ProviderAttempt(
                attempt_number=1,
                status=default_status,
                metrics=getattr(provider, "last_metrics", ProviderMetrics()),
                diagnostic=getattr(provider, "last_diagnostic", None),
            )
        ]
        for attempt in attempts:
            number = int(getattr(attempt, "attempt_number", 1))
            target = first_call
            if number != first_call.attempt_number:
                target = ModelCallORM(
                    translation_job_id=first_call.translation_job_id,
                    translation_chunk_id=first_call.translation_chunk_id,
                    attempt_number=number,
                    provider=first_call.provider,
                    model_name=first_call.model_name,
                    prompt_version=first_call.prompt_version,
                    system_prompt=first_call.system_prompt,
                    user_prompt=first_call.user_prompt,
                    source_text=first_call.source_text,
                    context_snapshot_json=first_call.context_snapshot_json,
                    previous_translation_tail=first_call.previous_translation_tail,
                    prompt_hash=first_call.prompt_hash,
                    status=getattr(attempt, "status", default_status),
                )
                session.add(target)
            target.status = getattr(attempt, "status", default_status)
            metrics = getattr(attempt, "metrics", None)
            if metrics is not None:
                target.prompt_tokens = metrics.prompt_tokens
                target.output_tokens = metrics.output_tokens
                target.duration_ms = metrics.duration_ms
            diagnostic = getattr(attempt, "diagnostic", None)
            if target.status == "failed" and diagnostic is not None:
                target.diagnostic_json = diagnostic.model_dump()
            if target.status == "completed" and response is not None:
                target.response_json = response.model_dump(exclude_none=True)
                target.translated_text = response.translation

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
