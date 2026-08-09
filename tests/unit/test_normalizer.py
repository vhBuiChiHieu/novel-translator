from novel_translator.domain.context.normalizer import normalize_update
from novel_translator.domain.model.enums import ContextType
from novel_translator.schemas.context_update import ContextUpdate


def test_normalizer_deduplicates_aliases_and_removes_canonical_values() -> None:
    result = normalize_update(
        ContextUpdate(
            type=ContextType.CHARACTER,
            source="  林凡 ",
            translation=" Lâm Phàm ",
            aliases=["林凡", "  Tiểu Lâm  ", "Tiểu Lâm", "Lâm Phàm"],
        )
    )
    assert result.source == "林凡"
    assert result.translation == "Lâm Phàm"
    assert result.aliases == ["Tiểu Lâm"]
