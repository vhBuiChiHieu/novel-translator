import typer

from novel_translator.ui.app import run_desktop

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
def desktop() -> None:
    """Open the native Novel Translator desktop application."""
    run_desktop()
