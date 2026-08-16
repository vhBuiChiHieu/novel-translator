from novel_translator.config import ContextSettings
from novel_translator.domain.context.policies import should_auto_confirm
from novel_translator.domain.model.enums import ContextType
from novel_translator.schemas.context_update import ContextUpdate


def test_default_minimum_confidence_is_0_8() -> None:
    assert ContextSettings().minimum_confidence == 0.8


def test_auto_confirm_checks_present_confidence_against_0_8() -> None:
    settings = ContextSettings()

    assert should_auto_confirm(
        ContextUpdate(type=ContextType.CHARACTER, source="陆沉", confidence=0.8),
        "陆沉 xuất hiện trong đoạn văn.",
        settings,
    )
    assert not should_auto_confirm(
        ContextUpdate(type=ContextType.CHARACTER, source="陆沉", confidence=0.79),
        "陆沉 xuất hiện trong đoạn văn.",
        settings,
    )


def test_auto_confirm_accepts_update_without_confidence() -> None:
    assert should_auto_confirm(
        ContextUpdate(type=ContextType.CHARACTER, source="陆沉"),
        "陆沉 xuất hiện trong đoạn văn.",
        ContextSettings(),
    )
