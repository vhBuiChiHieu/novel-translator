from pathlib import Path
from typing import Annotated

import typer

from novel_translator.application.services.context_service import ContextService

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_context(
    context_type: Annotated[str | None, typer.Option("--type")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
) -> None:
    """List persisted entity and term mappings."""
    rows = ContextService().list_items(context_type, status)
    for item_type, source, translation, item_status in rows:
        typer.echo(f"{item_type:12} {item_status:10} {source} = {translation or ''}")


@app.command("import")
def import_context(path: Path) -> None:
    """Import confirmed mappings from a YAML file."""
    typer.echo(f"Imported {ContextService().import_yaml(path)} context item(s).")


@app.command("export")
def export_context() -> None:
    """Export persisted mappings to exports/context.yaml."""
    typer.echo(ContextService().export_yaml())


@app.command("conflicts")
def conflicts() -> None:
    """List context conflicts without overwriting confirmed mappings."""
    for conflict in ContextService().conflicts():
        typer.echo(
            f"{conflict.id}: {conflict.status} {conflict.context_type} {conflict.source_key}: "
            f"{conflict.existing_value} <> {conflict.candidate_value}"
        )


@app.command("resolve")
def resolve(conflict_id: int) -> None:
    """Interactively resolve one open conflict."""
    service = ContextService()
    conflict = next((item for item in service.conflicts() if item.id == conflict_id and item.status == "open"), None)
    if conflict is None:
        raise typer.BadParameter(f"Open conflict {conflict_id} was not found")
    typer.echo(f"Existing: {conflict.existing_value}\nCandidate: {conflict.candidate_value}")
    choice = typer.prompt("[1] Keep existing [2] Accept candidate [3] Custom [4] Cancel", default="4")
    if choice == "1":
        service.resolve(conflict_id, "existing")
    elif choice == "2":
        service.resolve(conflict_id, "candidate")
    elif choice == "3":
        service.resolve(conflict_id, "custom", typer.prompt("Custom translation"))
    elif choice != "4":
        raise typer.BadParameter("Choose 1, 2, 3, or 4")
