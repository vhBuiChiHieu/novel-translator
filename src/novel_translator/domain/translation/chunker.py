from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceChunk:
    index: int
    text: str


def normalize_source(text: str) -> str:
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


class ParagraphChapterChunker:
    def __init__(self, target_chars: int, max_chars: int, min_chars: int) -> None:
        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars

    def split(self, source_text: str) -> list[SourceChunk]:
        paragraphs = [p for p in re.split(r"\n\s*\n", source_text) if p.strip()]
        units = [piece for paragraph in paragraphs for piece in self._split_oversized(paragraph)]
        chunks: list[str] = []
        current = ""
        for unit in units:
            proposed = f"{current}\n\n{unit}" if current else unit
            if current and len(proposed) > self.max_chars:
                chunks.append(current)
                current = unit
            elif current and len(current) >= self.target_chars:
                chunks.append(current)
                current = unit
            else:
                current = proposed
        if current:
            if chunks and len(current) < self.min_chars and len(chunks[-1]) + 2 + len(current) <= self.max_chars:
                chunks[-1] = f"{chunks[-1]}\n\n{current}"
            else:
                chunks.append(current)
        return [SourceChunk(index=index, text=text) for index, text in enumerate(chunks)]

    def _split_oversized(self, paragraph: str) -> list[str]:
        if len(paragraph) <= self.max_chars:
            return [paragraph]
        sentences = re.split(r"(?<=[。！？；])|(?<=……)", paragraph)
        pieces: list[str] = []
        current = ""
        for sentence in (s for s in sentences if s):
            if current and len(current) + len(sentence) > self.max_chars:
                pieces.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            pieces.append(current)
        result: list[str] = []
        for piece in pieces:
            result.extend(piece[i : i + self.max_chars] for i in range(0, len(piece), self.max_chars))
        return result
