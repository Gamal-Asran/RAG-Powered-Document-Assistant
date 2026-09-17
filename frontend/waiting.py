"""Responsive event pumping and elapsed-time updates for streamed queries."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, Queue
from time import monotonic
from typing import TypeVar, cast


NEUTRAL_WAITING_MESSAGES = (
    "Working locally...",
    "Processing your request...",
    "This may take a few minutes...",
)
MESSAGE_ROTATION_SECONDS = 6

EventT = TypeVar("EventT")
_STREAM_DONE = object()


@dataclass(frozen=True, slots=True)
class _StreamFailure:
    error: Exception


@dataclass(frozen=True, slots=True)
class WaitingStatus:
    message: str
    elapsed_seconds: int

    @property
    def elapsed_text(self) -> str:
        minutes, seconds = divmod(self.elapsed_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"


def waiting_status(elapsed_seconds: float) -> WaitingStatus:
    elapsed = max(0, int(elapsed_seconds))
    message_index = (elapsed // MESSAGE_ROTATION_SECONDS) % len(NEUTRAL_WAITING_MESSAGES)
    return WaitingStatus(NEUTRAL_WAITING_MESSAGES[message_index], elapsed)


def pump_stream(
    event_source: Callable[[], Iterable[EventT]],
    on_event: Callable[[EventT], None],
    on_tick: Callable[[WaitingStatus], None],
    *,
    poll_interval: float = 0.1,
) -> None:
    """Read a blocking event stream off-thread and dispatch its events in order."""
    events: Queue[object] = Queue()

    def produce() -> None:
        try:
            for event in event_source():
                events.put(event)
        except Exception as exc:
            events.put(_StreamFailure(exc))
        finally:
            events.put(_STREAM_DONE)

    started = monotonic()
    last_tick = -1
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="frontend-stream") as executor:
        executor.submit(produce)
        while True:
            try:
                item = events.get(timeout=poll_interval)
            except Empty:
                item = None
            status = waiting_status(monotonic() - started)
            if status.elapsed_seconds != last_tick:
                on_tick(status)
                last_tick = status.elapsed_seconds
            if item is None:
                continue
            if item is _STREAM_DONE:
                return
            if isinstance(item, _StreamFailure):
                raise item.error
            on_event(cast(EventT, item))
