# Novel Translator

## Tech stack

- Python 3.12 with src-layout packaging; CLI entry point is `novel`.
- Typer — command-line interface; Pydantic 2 + pydantic-settings — validated schemas and configuration.
- SQLite + SQLAlchemy 2.x — local persistence; Alembic — production schema migrations.
- Ollama `/api/chat` and DeepSeek Chat Completions + httpx — model providers; model output is validated as Pydantic data.
- Jinja2 — versioned translation prompts; PyYAML — `novel.yaml` and manual context import/export.
- PySide6 desktop UI with `QThreadPool` workers; `keyring` stores the DeepSeek credential outside `novel.yaml`.
- Local web UI with a FastAPI backend and React/Vite frontend; the web server binds to loopback only.
- pytest + respx/`httpx.MockTransport` — tests; Ruff and mypy — required static quality checks.

## Architecture

- `src/novel_translator/domain/` — business rules, context logic, enums; must not depend on SQLAlchemy, httpx, filesystem, or Typer.
- `application/services/` — use-case orchestration; chapter translation flow starts at `translation_service.py`.
- `application/facade.py` and `application/session.py` — UI-facing API and immutable project scope; UI code must not access SQLAlchemy models directly.
- `infrastructure/persistence/` — SQLite/SQLAlchemy adapter and Alembic migration; project databases upgrade through `migrate.py`.
- `ModelCallORM` records one sanitized audit entry per provider attempt, including rendered prompts, parsed response, metrics, and diagnostics.
- `infrastructure/model/` — Ollama and DeepSeek HTTP adapters plus the provider factory; adapters must never write to the database.
- `infrastructure/prompting/jinja_prompt_builder.py` — loads and renders the versioned prompt template.
- `schemas/` — Pydantic model I/O; `ContextUpdate` and `TranslationResponse` are the structured model-output contract.
- `prompts/translation_v*.jinja2` — immutable versioned templates; select them through `translation.prompt_version`, persist the version on new jobs, and render resumed jobs with their persisted version.
- `infrastructure/model/diagnostics.py` — sanitize provider response diagnostics before they are logged or persisted; never log credentials.
- `cli/` — Typer bootstrap interface; `novel init <name>` is the only CLI command.
- `ui/` — native desktop application; long-running import, translation, and export work must run in `FunctionWorker`, while widget updates stay on the UI thread.
- `src/novel_translator/web/` — local FastAPI adapter; routes use `ApplicationFacade`/`ProjectSession` and serializers, and must not access SQLAlchemy ORM objects directly.
- `src/novel_translator/web/runtime.py` — process-scoped project/session runtime, one mutation queue, background operations, cancellation boundaries, and SSE event replay.
- `src/novel_translator/web/static/` — checked-in production bundle served by FastAPI; keep it synchronized with `web-client/dist/` after frontend builds.
- `web-client/` — React/Vite frontend; browser state uses the versioned API under `/api/v1` and receives live operation updates through SSE.
- `tests/unit`, `tests/integration`, `tests/provider` — core logic, project/SQLite flow, and mocked model-provider HTTP tests.
- `tests/unit/test_web_runtime.py`, `tests/integration/test_web_api.py`, and `web-client/tests/` — web runtime/API/frontend coverage, including the Playwright smoke test.

## Key runtime behavior

- `novel init <name>` — creates `./<name>`; use `cd <name>` before import, translation, context, or export commands.
- `novel-translator` — opens the desktop UI; install it with `pip install -e ".[desktop,dev]"` when PySide6/keyring are not already installed.
- `novel-web` — starts the local web UI on `127.0.0.1`; with no `--project`, the browser opens the project picker and the user enters an absolute path containing `novel.yaml`. `--project <path>` opens a project directly.
- Install web dependencies with `pip install -e "[web,dev]"`; use `novel-web --no-open` in automated/headless environments.
- Import, translation, context management, and export are UI-only workflows exposed by both the desktop and local web UIs.
- The web launch token is one-time; subsequent API access requires the local app token/session cookie. Do not add network binding, CORS, API docs, credential values, or unredacted provider diagnostics.
- Web mutations are queued and serialized per process; long-running work stays off the request thread, emits progress through SSE, and must honor cancellation at safe chunk/operation boundaries.
- `translation_service.py` — process chunks sequentially, emit progress/project logs, persist context snapshots/metrics, and use a final transaction for chunk response, context merges, conflicts, and completion state.
- Provider failures — log the sanitized raw response before retrying or failing; failed chunks persist the final diagnostic in `raw_model_response_json`.
- `domain/context/merger.py` — confirmed mappings are authoritative; translation conflicts create records rather than overwrite mappings.
- `domain/context/retriever.py` — retrieves confirmed exact source/alias matches and expands relationships only one level.

## Commands

- `pip install -e ".[dev]"` — install runtime and test tooling.
- `pip install -e ".[web,dev]"` — install the local web server and web test dependencies.
- `novel-web [--project PATH] [--port PORT] [--no-open]` — run the local web application; keep the bind address at `127.0.0.1`.
- `cd web-client; npm ci; npm run lint; npm test; npm run build` — install, validate, test, and build the frontend. Copy the resulting bundle into `src/novel_translator/web/static/` when the checked-in serving artifact changes.
- `cd web-client; npm run e2e` — run the Playwright smoke test; set `PLAYWRIGHT_EXECUTABLE_PATH` when using an existing local Chrome instead of an installed Playwright browser.
- `ruff check . && mypy src/novel_translator --exclude migrations && pytest -q` — required quality gate.
- Run test commands from repository root; integration fixtures change the working directory only inside individual tests.

## Sandbox

- If a tool call is denied by the sandbox, immediately request escalated approval with a concise justification before retrying it.

## CodeGraph

Khi repository có thư mục `.codegraph/` ở root, phải dùng CodeGraph trước khi dùng `rg`, `grep`, `find` hoặc đọc file để tìm hiểu hay định vị mã nguồn:

- Ưu tiên MCP `codegraph_explore` nếu có; công cụ này trả về source liên quan kèm call path.
- Nếu không có MCP, dùng `codegraph explore "<symbols hoặc câu hỏi>"` trong shell.
- Chỉ bỏ qua CodeGraph khi repository không có thư mục `.codegraph/`.
