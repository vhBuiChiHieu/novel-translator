from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_translator.config import default_yaml, load_project_settings


def write_project_config(project: Path, model: str = "provider: deepseek\n  name: deepseek-v4-flash") -> None:
    (project / "novel.yaml").write_text(
        f"project:\n  name: demo\nmodel:\n  {model}\n",
        encoding="utf-8",
    )


def test_loads_deepseek_api_key_from_environment(tmp_path: Path, monkeypatch) -> None:
    write_project_config(tmp_path)
    monkeypatch.setenv("NOVEL_TRANSLATOR_DEEPSEEK_API_KEY", "secret-token")

    settings = load_project_settings(tmp_path)

    assert settings.model.provider == "deepseek"
    assert settings.model.name == "deepseek-v4-flash"
    assert settings.model.api_key is not None
    assert settings.model.api_key.get_secret_value() == "secret-token"
    assert "api_key" not in settings.model.model_dump()


def test_default_yaml_does_not_include_api_key() -> None:
    assert "api_key" not in default_yaml("demo")["model"]


def test_default_yaml_omits_optional_model_tuning_values() -> None:
    assert default_yaml("demo")["model"]["options"] == {}


def test_loads_translation_prompt_version(tmp_path: Path) -> None:
    (tmp_path / "novel.yaml").write_text(
        "project:\n  name: demo\ntranslation:\n  prompt_version: translation-v2\n",
        encoding="utf-8",
    )

    assert load_project_settings(tmp_path).prompt_version == "translation-v2"


def test_loads_log_level_from_project_yaml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOVEL_TRANSLATOR_LOG_LEVEL", raising=False)
    (tmp_path / "novel.yaml").write_text(
        "project:\n  name: demo\nlog_level: DEBUG\n",
        encoding="utf-8",
    )

    assert default_yaml("demo")["log_level"] == "INFO"
    assert load_project_settings(tmp_path).log_level == "DEBUG"


def test_rejects_unsupported_translation_prompt_version(tmp_path: Path) -> None:
    (tmp_path / "novel.yaml").write_text(
        "project:\n  name: demo\ntranslation:\n  prompt_version: translation-v99\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="translation-v1"):
        load_project_settings(tmp_path)


def test_missing_translation_prompt_version_defaults_to_v1(tmp_path: Path) -> None:
    write_project_config(tmp_path)

    assert load_project_settings(tmp_path).prompt_version == "translation-v1"


def test_ignores_api_key_from_project_configuration(tmp_path: Path, monkeypatch) -> None:
    write_project_config(tmp_path, "provider: deepseek\n  api_key: project-secret")
    monkeypatch.delenv("NOVEL_TRANSLATOR_DEEPSEEK_API_KEY", raising=False)
    try:
        import keyring
    except ImportError:
        pass
    else:
        monkeypatch.setattr(keyring, "get_password", lambda *_args: None)

    settings = load_project_settings(tmp_path)

    assert settings.model.api_key is None


def test_ollama_environment_overrides_remain_supported(tmp_path: Path, monkeypatch) -> None:
    write_project_config(tmp_path, "provider: ollama")
    monkeypatch.setenv("NOVEL_TRANSLATOR_OLLAMA_URL", "http://ollama.example")
    monkeypatch.setenv("NOVEL_TRANSLATOR_MODEL", "qwen3:32b")

    settings = load_project_settings(tmp_path)

    assert settings.model.base_url == "http://ollama.example"
    assert settings.model.name == "qwen3:32b"
