from pathlib import Path

import typer

from novel_translator.application.services.project_service import ProjectService

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(name: str) -> None:
    """Create a new project below the current directory."""
    path = ProjectService().init(Path.cwd(), name)
    typer.echo(f"Created project: {path}\nNext: cd {name}")
