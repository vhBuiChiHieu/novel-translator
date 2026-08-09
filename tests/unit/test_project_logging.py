import logging

import httpx
import pytest
from pydantic import SecretStr

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.deepseek_provider import DeepSeekProvider
from novel_translator.infrastructure.model.exceptions import ModelInvalidResponseError
from novel_translator.infrastructure.project_logging import configure_project_logging, shutdown_project_logging
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest


def test_async_project_logging_flushes_records(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "logs").mkdir(parents=True)
    log_path = project / "logs" / "novel-translator.log"

    configure_project_logging(project, "INFO")
    logging.getLogger("test").info("written asynchronously")
    shutdown_project_logging()

    assert "written asynchronously" in log_path.read_text(encoding="utf-8")


def test_project_log_includes_sanitized_invalid_provider_response(tmp_path, monkeypatch) -> None:
    # Alembic's test migration disables already-imported loggers.
    monkeypatch.setattr(logging.getLogger("novel_translator.infrastructure.model.deepseek_provider"), "disabled", False)
    shutdown_project_logging()
    project = tmp_path / "project"
    (project / "logs").mkdir(parents=True)
    log_path = project / "logs" / "novel-translator.log"
    request = TranslationRequest(
        system_prompt="system",
        user_prompt="user",
        source_text="中文",
        context_snapshot=ContextSnapshot(),
    )
    provider = DeepSeekProvider(
        ModelSettings(provider="deepseek", api_key=SecretStr("token"), max_retries=0),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "bad"}}], "token": "secret-token"},
                )
            )
        ),
    )

    configure_project_logging(project, "INFO")
    with pytest.raises(ModelInvalidResponseError):
        provider.translate(request)
    shutdown_project_logging()

    contents = log_path.read_text(encoding="utf-8")
    assert "DeepSeek request failed after 1 attempt(s)" in contents
    assert 'raw_response={"choices": [{"message": {"content": "bad"}}], "token": "[redacted]"}' in contents
    assert "secret-token" not in contents
