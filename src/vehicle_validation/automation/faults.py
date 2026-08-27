"""Reproducible fault injection helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from random import Random

from vehicle_validation.canbus.protocol import CanFrame


@dataclass(frozen=True)
class DelayedFrame:
    frame: CanFrame
    release_tick: int
    reason: str


class MessageDelayInjector:
    """Delay matching CAN frames with deterministic pseudo-random selection."""

    def __init__(
        self,
        target_ids: set[int],
        delay_ticks: int,
        probability: float = 1.0,
        seed: int = 1,
    ) -> None:
        if delay_ticks < 0:
            raise ValueError("delay_ticks must be non-negative")
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in range 0..1")
        self.target_ids = target_ids
        self.delay_ticks = delay_ticks
        self.probability = probability
        self.random = Random(seed)
        self.current_tick = 0
        self._queue: deque[DelayedFrame] = deque()

    def inject(self, frame: CanFrame) -> list[CanFrame]:
        due = self.advance()
        if frame.arbitration_id in self.target_ids and self.random.random() <= self.probability:
            self._queue.append(
                DelayedFrame(
                    frame=frame,
                    release_tick=self.current_tick + self.delay_ticks,
                    reason=f"delay:{frame.arbitration_id:#05x}",
                )
            )
            return due
        return [*due, frame]

    def advance(self) -> list[CanFrame]:
        self.current_tick += 1
        released: list[CanFrame] = []
        while self._queue and self._queue[0].release_tick <= self.current_tick:
            released.append(self._queue.popleft().frame)
        return released

    @property
    def pending_count(self) -> int:
        return len(self._queue)
