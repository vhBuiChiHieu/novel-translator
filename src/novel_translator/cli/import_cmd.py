from pathlib import Path

import typer

from novel_translator.application.services.import_service import ImportService

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def import_chapters(directory: Path) -> None:
    """Import chapter_XXXX.txt files from DIRECTORY."""
    count = ImportService().import_directory(directory)
    typer.echo(f"Imported {count} chapter(s).")
