from pathlib import Path
from threading import RLock

from alembic import command
from alembic.config import Config

_migration_lock = RLock()


def upgrade_database(database_path: Path) -> None:
    """Upgrade one project database through the packaged Alembic migration."""
    with _migration_lock:
        root = Path(__file__).resolve().parents[4]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
        command.upgrade(config, "head")
