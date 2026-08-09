import typer

from novel_translator.application.services.translation_service import TranslationService

app = typer.Typer(no_args_is_help=True)


@app.command()
def translate(
    chapter: int,
    resume: bool = typer.Option(False, "--resume"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Translate one imported chapter."""
    job = TranslationService().translate(chapter, resume=resume, force=force)
    typer.echo(
        f"Chapter {chapter} completed\n\n"
        f"Prompt tokens: {job.total_prompt_tokens:,}\n"
        f"Output tokens: {job.total_output_tokens:,}\n"
        f"Duration: {job.total_duration_ms} ms"
    )


@app.command("translate-range")
def translate_range(first: int, last: int) -> None:
    """Translate a sequential range so earlier context is available later."""
    service = TranslationService()
    for chapter in range(first, last + 1):
        service.translate(chapter)
        typer.echo(f"Translated chapter {chapter}")
