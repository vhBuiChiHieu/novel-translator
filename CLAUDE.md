# Novel Translator

## Tech stack

- Python 3.12 with src-layout packaging; CLI entry point is `novel`.
- Typer — command-line interface; Pydantic 2 + pydantic-settings — validated schemas and configuration.
- SQLite + SQLAlchemy 2.x — local persistence; Alembic — production schema migrations.
- Ollama `/api/chat` and DeepSeek Chat Completions + httpx — model providers; model output is validated as Pydantic data.
- Jinja2 — versioned translation prompts; PyYAML — `novel.yaml` and manual context import/export.
- pytest + respx/`httpx.MockTransport` — tests; Ruff and mypy — required static quality checks.

## Architecture

- `src/novel_translator/domain/` — business rules, context logic, enums; must not depend on SQLAlchemy, httpx, filesystem, or Typer.
- `application/services/` — use-case orchestration; chapter translation flow starts at `translation_service.py`.
- `infrastructure/persistence/` — SQLite/SQLAlchemy adapter and Alembic migration; project databases upgrade through `migrate.py`.
- `infrastructure/model/` — Ollama and DeepSeek HTTP adapters plus the provider factory; adapters must never write to the database.
- `infrastructure/prompting/jinja_prompt_builder.py` — loads and renders the versioned prompt template.
- `schemas/` — Pydantic model I/O; `ContextUpdate` and `TranslationResponse` are the structured model-output contract.
- `prompts/translation_v*.jinja2` — immutable versioned templates; select them through `translation.prompt_version`, persist the version on new jobs, and render resumed jobs with their persisted version.
- `infrastructure/model/diagnostics.py` — sanitize provider response diagnostics before they are logged or persisted; never log credentials.
- `cli/` — Typer interface; commands other than `init` require the current directory to contain `novel.yaml`.
- `tests/unit`, `tests/integration`, `tests/provider` — core logic, project/SQLite flow, and mocked model-provider HTTP tests.

## Key runtime behavior

- `novel init <name>` — creates `./<name>`; use `cd <name>` before import, translation, context, or export commands.
- `translation_service.py` — process chunks sequentially, emit progress/project logs, persist context snapshots/metrics, and use a final transaction for chunk response, context merges, conflicts, and completion state.
- Provider failures — log the sanitized raw response before retrying or failing; failed chunks persist the final diagnostic in `raw_model_response_json`.
- `domain/context/merger.py` — confirmed mappings are authoritative; translation conflicts create records rather than overwrite mappings.
- `domain/context/retriever.py` — retrieves confirmed exact source/alias matches and expands relationships only one level.

## Commands

- `pip install -e ".[dev]"` — install runtime and test tooling.
- `ruff check . && mypy src/novel_translator --exclude migrations && pytest -q` — required quality gate.
- Run test commands from repository root; integration fixtures change the working directory only inside individual tests.

## Gotchas

- Production schema initialization must use Alembic; do not replace it with `Base.metadata.create_all()`.
- SQLAlchemy currently emits `datetime.utcnow()` deprecation warnings; new timestamp code should prefer timezone-aware UTC.
