import pytest

from novel_translator.config import ProjectSettings
from novel_translator.infrastructure.prompting.jinja_prompt_builder import JinjaPromptBuilder
from novel_translator.schemas.context_snapshot import ContextSnapshot


def build_prompt(prompt_version: str):
    return JinjaPromptBuilder(prompt_version).build(
        ProjectSettings(project_name="demo"),
        source_text="陆沉来到小寒城。",
        snapshot=ContextSnapshot(),
        previous_translation_tail="",
    )


def test_builder_renders_selected_prompt_version() -> None:
    v1 = build_prompt("translation-v1")
    v2 = build_prompt("translation-v2")

    assert "## RESPONSE FORMAT" not in v1.request.user_prompt
    assert "## RESPONSE FORMAT" in v2.request.user_prompt
    assert v1.prompt_hash != v2.prompt_hash


def test_builder_rejects_unsupported_prompt_version() -> None:
    with pytest.raises(ValueError, match="Unsupported prompt version"):
        JinjaPromptBuilder("translation-v99")
