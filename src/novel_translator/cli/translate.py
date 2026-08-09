import typer

from novel_translator.application.services.translation_service import TranslationProgress, TranslationService

app = typer.Typer(no_args_is_help=True)


def print_progress(progress: TranslationProgress) -> None:
    chunk_number = (progress.chunk_index or 0) + 1
    if progress.event == "job_started":
        message = f"Chapter {progress.chapter_number}: started ({progress.total_chunks} chunks)"
    elif progress.event == "chunk_started":
        message = f"Chapter {progress.chapter_number}: chunk {chunk_number}/{progress.total_chunks} translating"
    elif progress.event == "chunk_completed":
        message = (
            f"Chapter {progress.chapter_number}: chunk {chunk_number}/{progress.total_chunks} "
            f"completed ({progress.duration_ms} ms)"
        )
    elif progress.event == "chunk_failed":
        message = f"Chapter {progress.chapter_number}: chunk {chunk_number}/{progress.total_chunks} failed: {progress.error}"
    else:
        message = f"Chapter {progress.chapter_number}: completed"
    typer.echo(message, err=True)


@app.command()
def translate(
    chapter: int,
    resume: bool = typer.Option(False, "--resume"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Translate one imported chapter."""
    job = TranslationService().translate(chapter, resume=resume, force=force, on_progress=print_progress)
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
