"""Structured automation run results."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter


@dataclass(frozen=True)
class StepResult:
    name: str
    passed: bool
    duration_seconds: float
    details: str = ""


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_seconds: float
    steps: list[StepResult] = field(default_factory=list)
    failure_reason: str = ""


class Stopwatch:
    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self._start
