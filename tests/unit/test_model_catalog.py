from novel_translator.domain.model.catalog import model_catalog, model_options_for


def test_model_catalog_excludes_ollama_and_lists_current_cloud_models() -> None:
    catalog = model_catalog()

    assert catalog["ollama"] == []
    assert [option["id"] for option in catalog["deepseek"]] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert catalog["gemini"][0]["id"] == "gemini-3.7-flash"


def test_model_options_for_unknown_provider_is_empty() -> None:
    assert model_options_for("unknown") == []
