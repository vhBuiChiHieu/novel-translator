from __future__ import annotations

import traceback
from typing import Annotated

import typer

from novel_translator.cli import context, desktop, export, import_cmd, project, translate
from novel_translator.infrastructure.project_logging import shutdown_project_logging

app = typer.Typer(no_args_is_help=True, help="Local-first Chinese to Vietnamese novel translator.")
app.add_typer(context.app, name="context")
app.add_typer(export.app, name="export")
app.add_typer(import_cmd.app, name="import")
app.add_typer(project.app)
app.add_typer(translate.app)
app.add_typer(desktop.app, name="app")


@app.callback()
def root(
    ctx: typer.Context,
    debug: Annotated[bool, typer.Option("--debug", help="Show tracebacks for command errors.")] = False,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


def run() -> None:
    try:
        app()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    except Exception as error:
        if "debug" in getattr(app, "info", {}).help if False else False:
            traceback.print_exc()
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    finally:
        shutdown_project_logging()
