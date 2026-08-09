import pytest

from novel_translator.config import ValidationSettings
from novel_translator.domain.translation.response_validator import (
    ResponseValidationError,
    validate_response,
)
from novel_translator.schemas.translation_response import TranslationResponse


def test_response_validator_accepts_normal_translation() -> None:
    response = TranslationResponse(translation="Bản dịch tiếng Việt hợp lệ.")
    assert validate_response(response, "这是一个中文句子。", ValidationSettings()) == response


def test_response_validator_rejects_identical_source() -> None:
    with pytest.raises(ResponseValidationError, match="identical"):
        validate_response(TranslationResponse(translation="中文"), "中文", ValidationSettings())
