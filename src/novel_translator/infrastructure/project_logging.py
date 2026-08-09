from __future__ import annotations

import logging
import queue
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path

_listener: QueueListener | None = None
_queue_handler: QueueHandler | None = None
_log_path: Path | None = None


class FlushingFileHandler(logging.FileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def configure_project_logging(project_path: Path, level: str) -> None:
    global _listener, _log_path, _queue_handler

    log_path = project_path / "logs" / "novel-translator.log"
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if _listener is not None and _log_path == log_path:
        return
    shutdown_project_logging()

    file_handler = FlushingFileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    records: queue.Queue[logging.LogRecord] = queue.Queue()
    _queue_handler = QueueHandler(records)
    root.handlers.clear()
    root.addHandler(_queue_handler)
    _listener = QueueListener(records, file_handler, respect_handler_level=True)
    _listener.start()
    _log_path = log_path


def shutdown_project_logging() -> None:
    global _listener, _log_path, _queue_handler

    root = logging.getLogger()
    if _queue_handler is not None:
        root.removeHandler(_queue_handler)
    if _listener is not None:
        _listener.stop()
    _listener = None
    _queue_handler = None
    _log_path = None
