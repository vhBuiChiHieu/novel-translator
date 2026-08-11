import sys
import types
from pathlib import Path

from novel_translator.application.facade import ApplicationFacade
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.services.translation_service import TranslationService
from novel_translator.infrastructure.model.provider import ProviderMetrics
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


class FakeProvider:
    last_metrics = ProviderMetrics(prompt_tokens=3, output_tokens=2, duration_ms=7)
    last_diagnostic = None

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(translation="Bản dịch kiểm thử hợp lệ.")


def test_facade_opens_project_from_explicit_path_and_exposes_audit(tmp_path: Path) -> None:
    project = ProjectService().init(tmp_path, "demo")
    input_dir = tmp_path / "chapters"
    input_dir.mkdir()
    (input_dir / "chapter_0001.txt").write_text("第一章 có nội dung.", encoding="utf-8")

    facade = ApplicationFacade(project)
    assert facade.get_dashboard().health_ok
    previews = facade.preview_import(input_dir)
    assert previews[0].valid_utf8
    assert facade.import_chapters(input_dir) == 1

    facade.upsert_context("character", "第一章", "Chương Một")
    assert facade.list_context("character")[0].translation == "Chương Một"
    assert "entity" in facade.list_database_tables()
    entity_table = facade.get_database_table("entity")
    assert entity_table.columns[:3] == ["id", "novel_id", "entity_type"]
    assert entity_table.rows[0]["source_name"] == "第一章"
    facade.update_settings({"model": {"name": "test-model"}})
    assert facade.session.settings.model.name == "test-model"

    TranslationService(FakeProvider(), session=facade.session).translate(1)
    calls = facade.list_model_calls()
    assert len(calls) == 1
    assert calls[0].system_prompt
    assert calls[0].user_prompt
    assert calls[0].translated_text == "Bản dịch kiểm thử hợp lệ."

    facade.delete_context("character", "第一章")
    assert facade.list_context("character") == []


def test_setting_api_key_refreshes_open_session(tmp_path: Path, monkeypatch) -> None:
    stored: dict[str, str] = {}
    keyring = types.ModuleType("keyring")
    keyring.set_password = lambda _service, username, value: stored.__setitem__(username, value)
    keyring.get_password = lambda _service, username: stored.get(username)
    keyring.delete_password = lambda _service, username: stored.pop(username, None)
    monkeypatch.setitem(sys.modules, "keyring", keyring)
    monkeypatch.delenv("NOVEL_TRANSLATOR_DEEPSEEK_API_KEY", raising=False)

    project = ProjectService().init(tmp_path, "demo")
    facade = ApplicationFacade(project)
    facade.update_settings({"model": {"provider": "deepseek"}})
    facade.set_api_key("secret-from-ui")

    assert facade.session.settings.model.api_key is not None
    assert facade.session.settings.model.api_key.get_secret_value() == "secret-from-ui"


def test_reset_project_removes_novel_data_but_preserves_configuration(tmp_path: Path) -> None:
    project = ProjectService().init(tmp_path, "demo")
    config_path = project / "novel.yaml"
    original_config = config_path.read_text(encoding="utf-8")
    input_dir = tmp_path / "chapters"
    input_dir.mkdir()
    (input_dir / "chapter_0001.txt").write_text("第一章", encoding="utf-8")

    facade = ApplicationFacade(project)
    facade.import_chapters(input_dir)
    (project / "translated" / "chapter_0001.txt").write_text("Chương Một", encoding="utf-8")
    (project / "exports" / "novel.txt").write_text("Bản cũ", encoding="utf-8")

    facade.reset_project()

    assert config_path.read_text(encoding="utf-8") == original_config
    assert facade.get_dashboard().health_ok
    assert facade.list_chapters() == []
    assert list((project / "source").iterdir()) == []
    assert list((project / "translated").iterdir()) == []
    assert list((project / "exports").iterdir()) == []
