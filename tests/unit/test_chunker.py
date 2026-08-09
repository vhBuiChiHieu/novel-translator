from novel_translator.domain.translation.chunker import ParagraphChapterChunker, normalize_source


def test_normalize_source_preserves_content_and_normalizes_layout() -> None:
    text = "﻿第一段  \r\n\r\n\r\n\r\n第二段\t\r\n"
    assert normalize_source(text) == "第一段\n\n\n第二段"


def test_chunker_keeps_paragraphs_and_reassembles() -> None:
    source = "甲甲\n\n乙乙\n\n丙丙"
    chunks = ParagraphChapterChunker(target_chars=3, max_chars=6, min_chars=1).split(source)
    assert [chunk.text for chunk in chunks] == ["甲甲\n\n乙乙", "丙丙"]
    assert [chunk.index for chunk in chunks] == [0, 1]


def test_chunker_splits_oversized_chinese_paragraph_on_sentence_boundaries() -> None:
    chunks = ParagraphChapterChunker(target_chars=8, max_chars=8, min_chars=1).split("甲甲。乙乙。丙丙。丁丁。")
    assert "".join(chunk.text for chunk in chunks) == "甲甲。乙乙。丙丙。丁丁。"
