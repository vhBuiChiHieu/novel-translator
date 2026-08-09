from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import resources

from jinja2 import Environment, StrictUndefined

from novel_translator.config import ProjectSettings
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest


@dataclass(frozen=True)
class RenderedPrompt:
    request: TranslationRequest
    prompt_hash: str


class JinjaPromptBuilder:
    def __init__(self) -> None:
        template_text = (
            resources.files("novel_translator.prompts").joinpath("translation_v1.jinja2").read_text("utf-8")
        )
        self.template = Environment(undefined=StrictUndefined, keep_trailing_newline=True).from_string(template_text)

    def build(
        self,
        settings: ProjectSettings,
        source_text: str,
        snapshot: ContextSnapshot,
        previous_translation_tail: str,
    ) -> RenderedPrompt:
        user_prompt = self.template.render(
            genre=settings.genre,
            source_text=source_text,
            previous_translation_tail=previous_translation_tail,
            **snapshot.model_dump(),
        )
        system_prompt = "You are a professional Chinese-to-Vietnamese web novel translator."
        request = TranslationRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            source_text=source_text,
            context_snapshot=snapshot,
        )
        return RenderedPrompt(request=request, prompt_hash=hashlib.sha256(user_prompt.encode("utf-8")).hexdigest())
