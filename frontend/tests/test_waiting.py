from __future__ import annotations

import pytest

from frontend.waiting import (
    MESSAGE_ROTATION_SECONDS,
    NEUTRAL_WAITING_MESSAGES,
    pump_stream,
    waiting_status,
)


def test_waiting_status_formats_elapsed_time() -> None:
    status = waiting_status(102.9)

    assert status.elapsed_seconds == 102
    assert status.elapsed_text == "01:42"


def test_waiting_messages_rotate_in_declared_order() -> None:
    messages = [
        waiting_status(index * MESSAGE_ROTATION_SECONDS).message
        for index in range(len(NEUTRAL_WAITING_MESSAGES))
    ]

    assert messages == list(NEUTRAL_WAITING_MESSAGES)
    assert waiting_status(len(NEUTRAL_WAITING_MESSAGES) * MESSAGE_ROTATION_SECONDS).message == messages[0]


def test_stream_events_are_dispatched_in_order_once() -> None:
    calls = 0
    received: list[str] = []

    def events():
        nonlocal calls
        calls += 1
        yield "sources"
        yield "answer"
        yield "completed"

    pump_stream(
        events,
        received.append,
        lambda status: None,
        poll_interval=0.001,
    )

    assert calls == 1
    assert received == ["sources", "answer", "completed"]


def test_stream_error_is_propagated_without_retry() -> None:
    calls = 0

    def events():
        nonlocal calls
        calls += 1
        raise RuntimeError("classified by the frontend error handler")
        yield  # pragma: no cover

    with pytest.raises(RuntimeError, match="classified by the frontend error handler"):
        pump_stream(events, lambda event: None, lambda status: None, poll_interval=0.001)

    assert calls == 1
