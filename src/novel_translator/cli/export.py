import typer

from novel_translator.application.services.export_service import ExportService

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def export_novel() -> None:
    """Concatenate translated chapters into exports/novel.txt."""
    typer.echo(ExportService().export())
