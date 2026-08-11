from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from novel_translator.application.services.project_service import ProjectService
from novel_translator.web.app import create_app
from novel_translator.web.runtime import WebRuntime


def authenticated_client(runtime: WebRuntime) -> TestClient:
    client = TestClient(create_app(runtime), base_url="http://127.0.0.1")
    response = client.post("/api/v1/session/bootstrap", headers={"X-Local-App-Token": runtime.startup_token})
    assert response.status_code == 200
    return client


def test_web_bootstrap_project_and_dashboard() -> None:
    with TemporaryDirectory() as temp:
        project = ProjectService().init(Path(temp), "web-demo")
        runtime = WebRuntime()
        with authenticated_client(runtime) as client:
            unauthenticated = TestClient(create_app(WebRuntime()), base_url="http://127.0.0.1")
            assert unauthenticated.get("/api/v1/dashboard").status_code == 401
            assert client.post("/api/v1/projects/open", json={"path": str(project)}).status_code == 200
            response = client.get("/api/v1/dashboard")
            assert response.status_code == 200
            assert response.json()["chapter_counts"] == {"total": 0, "imported": 0, "translated": 0, "failed": 0}
            settings = client.get("/api/v1/settings")
            assert settings.status_code == 200
            assert "api_key" not in settings.json()
            assert "secret" not in settings.text.lower()


def test_web_creates_and_opens_project() -> None:
    with TemporaryDirectory() as temp:
        runtime = WebRuntime()
        with authenticated_client(runtime) as client:
            response = client.post("/api/v1/projects/create", json={"parent_path": temp, "name": "created-web"})

            assert response.status_code == 201
            project_path = Path(response.json()["path"])
            assert project_path == Path(temp) / "created-web"
            assert (project_path / "novel.yaml").is_file()
            assert (project_path / "data" / "novel.db").is_file()
            assert client.get("/api/v1/projects/current").json()["project"]["project_name"] == "created-web"

            duplicate = client.post("/api/v1/projects/create", json={"parent_path": temp, "name": "created-web"})
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "PROJECT_EXISTS"


def test_web_rejects_invalid_project_name() -> None:
    with TemporaryDirectory() as temp:
        runtime = WebRuntime()
        with authenticated_client(runtime) as client:
            response = client.post("/api/v1/projects/create", json={"parent_path": temp, "name": "nested\\project"})

            assert response.status_code == 422
            assert response.json()["error"]["code"] == "PROJECT_NAME_INVALID"


def test_web_picks_directory(monkeypatch, tmp_path) -> None:
    selected = tmp_path / "picked-project"
    selected.mkdir()
    monkeypatch.setattr("novel_translator.web.routes.projects.choose_directory", lambda *, title: selected)

    runtime = WebRuntime()
    with authenticated_client(runtime) as client:
        response = client.post("/api/v1/projects/pick", json={"purpose": "project"})

    assert response.status_code == 200
    assert response.json() == {"path": str(selected.resolve())}

    source_response = client.post("/api/v1/projects/pick", json={"purpose": "source"})
    assert source_response.status_code == 200
    assert source_response.json() == {"path": str(selected.resolve())}


def test_web_rejects_non_loopback_origin() -> None:
    runtime = WebRuntime()
    with authenticated_client(runtime) as client:
        response = client.get("/api/v1/projects/current", headers={"Origin": "https://attacker.invalid"})
    assert response.status_code == 403
