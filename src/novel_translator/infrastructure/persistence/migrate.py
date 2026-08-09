from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_database(database_path: Path) -> None:
    """Upgrade one project database through the packaged Alembic migration."""
    root = Path(__file__).resolve().parents[4]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
