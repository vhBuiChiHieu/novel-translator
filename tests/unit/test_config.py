from pathlib import Path

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


def test_ignores_api_key_from_project_configuration(tmp_path: Path) -> None:
    write_project_config(tmp_path, "provider: deepseek\n  api_key: project-secret")

    settings = load_project_settings(tmp_path)

    assert settings.model.api_key is None


def test_ollama_environment_overrides_remain_supported(tmp_path: Path, monkeypatch) -> None:
    write_project_config(tmp_path, "provider: ollama")
    monkeypatch.setenv("NOVEL_TRANSLATOR_OLLAMA_URL", "http://ollama.example")
    monkeypatch.setenv("NOVEL_TRANSLATOR_MODEL", "qwen3:32b")

    settings = load_project_settings(tmp_path)

    assert settings.model.base_url == "http://ollama.example"
    assert settings.model.name == "qwen3:32b"
