from __future__ import annotations

from threading import Event

import pytest

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
