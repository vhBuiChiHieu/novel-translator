from __future__ import annotations

import logging
from threading import Event

import pytest

from novel_translator.infrastructure.project_logging import configure_project_logging, shutdown_project_logging
from novel_translator.web.errors import ProjectBusyError
from novel_translator.web.runtime import EventBroker, WebRuntime


def test_event_broker_marks_expired_last_event_id() -> None:
    broker = EventBroker(max_events=2)
    broker.publish("one", {"value": 1})
    broker.publish("two", {"value": 2})
    broker.publish("three", {"value": 3})

    events, stale = broker.since(0)

    assert stale is True
    assert [event.event for event in events] == ["two", "three"]


def test_runtime_allows_only_one_mutation(tmp_path) -> None:
    runtime = WebRuntime()
    runtime._project_path = tmp_path.resolve()
    started = Event()
    release = Event()

    operation = runtime.submit("test", lambda _: (started.set(), release.wait(2), {"ok": True})[-1])
    assert started.wait(2)
    with pytest.raises(ProjectBusyError):
        runtime.submit("test", lambda _: {})

    release.set()
    assert operation.future is not None
    operation.future.result(timeout=2)
    runtime.close()


def test_runtime_logs_failed_operation_to_project_file(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "logs").mkdir(parents=True)
    shutdown_project_logging()
    runtime_logger = logging.getLogger("novel_translator.web.runtime")
    runtime_logger.disabled = True
    configure_project_logging(project, "INFO")

    runtime = WebRuntime()
    runtime._project_path = project.resolve()

    def fail(_operation):
        raise ValueError("simulated operation failure")

    operation = runtime.submit("test_failure", fail)
    assert operation.future is not None
    operation.future.result(timeout=2)
    runtime.close()
    shutdown_project_logging()

    contents = (project / "logs" / "novel-translator.log").read_text(encoding="utf-8")
    assert operation.status == "failed"
    assert "Operation failed" in contents
    assert operation.operation_id in contents
    assert "VALIDATION_ERROR" in contents
