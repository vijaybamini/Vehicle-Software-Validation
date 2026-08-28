"""Thread-safe broadcast hub for live run progress events."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any


class ProgressHub:
    """Fan out run progress events to subscribed WebSocket clients.

    Progress events are produced from synchronous worker threads (the FastAPI
    thread pool) and delivered to async WebSocket readers on the event loop.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> None:
        payload = deepcopy(event)
        if self._loop is None:
            self._emit(payload)
            return
        self._loop.call_soon_threadsafe(self._emit, payload)

    def _emit(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(event)