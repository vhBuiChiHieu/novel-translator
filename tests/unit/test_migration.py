from __future__ import annotations

import threading
import time
from pathlib import Path

from novel_translator.infrastructure.persistence import migrate


def test_upgrade_database_serializes_alembic_calls(monkeypatch, tmp_path: Path) -> None:
    active = 0
    maximum_active = 0
    state_lock = threading.Lock()

    def fake_upgrade(_config, _revision) -> None:
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.02)
        with state_lock:
            active -= 1

    monkeypatch.setattr(migrate.command, "upgrade", fake_upgrade)
    threads = [
        threading.Thread(target=migrate.upgrade_database, args=(tmp_path / f"novel-{index}.db",))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert maximum_active == 1
