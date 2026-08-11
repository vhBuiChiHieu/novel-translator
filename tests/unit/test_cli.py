from typer.testing import CliRunner

from novel_translator.cli.app import app


def test_cli_exposes_only_init_command() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.stdout
    for removed_command in ("app", "context", "export", "import", "translate", "translate-range"):
        assert removed_command not in result.stdout
