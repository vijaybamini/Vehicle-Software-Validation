"""Structured automation run results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
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

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestRun:
    run_id: str
    started_at: str
    results: list[TestResult] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, run_id: str, metadata: dict[str, str] | None = None) -> "TestRun":
        return cls(
            run_id=run_id,
            started_at=datetime.now(UTC).isoformat(),
            metadata=metadata or {},
        )

    def add(self, result: TestResult) -> None:
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if not result.passed)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "metadata": self.metadata,
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
            },
            "results": [result.to_dict() for result in self.results],
        }


class Stopwatch:
    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self._start
