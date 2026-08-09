from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import select

from novel_translator.application.services.project_service import ProjectService
from novel_translator.domain.translation.chunker import normalize_source
from novel_translator.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from novel_translator.infrastructure.persistence.orm.models import ChapterORM

CHAPTER_PATTERN = re.compile(r"^chapter_(\d+)\.txt$", re.IGNORECASE)


class ImportService:
    def import_directory(self, source_directory: Path) -> int:
        settings = ProjectService().load_current()
        if not source_directory.is_dir():
            raise ValueError(f"Import directory does not exist: {source_directory}")
        candidates: list[tuple[int, Path]] = []
        for path in source_directory.iterdir():
            if path.suffix.lower() != ".txt":
                continue
            match = CHAPTER_PATTERN.fullmatch(path.name)
            if match is None:
                raise ValueError(f"Cannot parse chapter number from: {path.name}")
            candidates.append((int(match.group(1)), path))
        engine = create_sqlite_engine(settings.database_path)
        session_factory = create_session_factory(engine)
        novel = ProjectService().get_novel(settings)
        for number, path in sorted(candidates):
            try:
                source = normalize_source(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError as error:
                raise ValueError(f"Chapter is not valid UTF-8: {path}") from error
            target = settings.project_path / "source" / f"chapter_{number:04d}.txt"
            target.write_text(source + "\n", encoding="utf-8")
            source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            with session_factory() as session:
                chapter = session.scalar(
                    select(ChapterORM).where(
                        ChapterORM.novel_id == novel.id, ChapterORM.chapter_number == number
                    )
                )
                if chapter is None:
                    session.add(
                        ChapterORM(
                            novel_id=novel.id,
                            chapter_number=number,
                            source_path=str(target.relative_to(settings.project_path)),
                            source_hash=source_hash,
                            status="imported",
                        )
                    )
                else:
                    chapter.source_path = str(target.relative_to(settings.project_path))
                    chapter.source_hash = source_hash
                session.commit()
        return len(candidates)
