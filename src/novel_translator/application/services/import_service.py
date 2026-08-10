from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import select

from novel_translator.application.dtos import ChapterPreviewDTO
from novel_translator.application.project_scope import open_project_session
from novel_translator.application.session import ProjectSession
from novel_translator.domain.translation.chunker import normalize_source
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import ChapterORM

CHAPTER_PATTERN = re.compile(r"^chapter_(\d+)\.txt$", re.IGNORECASE)


class ImportService:
    def __init__(self, session: ProjectSession | None = None, project_path: Path | None = None) -> None:
        self.session = session
        self.project_path = project_path

    @staticmethod
    def preview_directory(source_directory: Path) -> list[ChapterPreviewDTO]:
        if not source_directory.is_dir():
            raise ValueError(f"Import directory does not exist: {source_directory}")
        previews: list[ChapterPreviewDTO] = []
        seen: set[int] = set()
        for path in sorted(source_directory.iterdir()):
            if path.suffix.lower() != ".txt":
                continue
            match = CHAPTER_PATTERN.fullmatch(path.name)
            if match is None:
                raise ValueError(f"Cannot parse chapter number from: {path.name}")
            number = int(match.group(1))
            if number in seen:
                raise ValueError(f"Duplicate chapter number in import directory: {number}")
            seen.add(number)
            try:
                source = normalize_source(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError as error:
                previews.append(
                    ChapterPreviewDTO(
                        chapter_number=number,
                        path=path,
                        valid_utf8=False,
                        error=f"Chapter is not valid UTF-8: {error}",
                    )
                )
            else:
                previews.append(
                    ChapterPreviewDTO(chapter_number=number, path=path, valid_utf8=True, source_text=source)
                )
        return previews

    def import_directory(self, source_directory: Path) -> int:
        active = open_project_session(self.session, self.project_path)
        settings = active.settings
        previews = self.preview_directory(source_directory)
        invalid = next((preview for preview in previews if not preview.valid_utf8), None)
        if invalid is not None:
            raise ValueError(invalid.error or f"Chapter {invalid.chapter_number} is not valid UTF-8")
        engine = create_sqlite_engine(settings.database_path)
        session_factory = create_session_factory(engine)
        for preview in previews:
            number = preview.chapter_number
            source = preview.source_text or ""
            target = settings.project_path / "source" / f"chapter_{number:04d}.txt"
            target.write_text(source + "\n", encoding="utf-8")
            source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            with session_factory() as session:
                chapter = session.scalar(
                    select(ChapterORM).where(
                        ChapterORM.novel_id == active.novel.id, ChapterORM.chapter_number == number
                    )
                )
                if chapter is None:
                    session.add(
                        ChapterORM(
                            novel_id=active.novel.id,
                            chapter_number=number,
                            source_path=str(target.relative_to(settings.project_path)),
                            source_hash=source_hash,
                            status="imported",
                        )
                    )
                else:
                    chapter.source_path = str(target.relative_to(settings.project_path))
                    if chapter.source_hash != source_hash:
                        chapter.translated_path = None
                        chapter.status = "imported"
                    chapter.source_hash = source_hash
                session.commit()
        return len(previews)
