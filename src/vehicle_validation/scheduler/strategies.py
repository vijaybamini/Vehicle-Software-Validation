"""Test scheduling strategies."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import ClassVar, Protocol


@dataclass(frozen=True)
class TestCase:
    __test__: ClassVar[bool] = False

    name: str
    estimated_duration_seconds: float = 1.0
    historical_failure_rate: float = 0.0
    priority: float = 0.0


class SchedulerStrategy(Protocol):
    name: str

    def order(self, tests: list[TestCase]) -> list[TestCase]:
        ...


class RandomStrategy:
    name = "random"

    def __init__(self, seed: int = 1) -> None:
        self.seed = seed

    def order(self, tests: list[TestCase]) -> list[TestCase]:
        shuffled = list(tests)
        Random(self.seed).shuffle(shuffled)
        return shuffled


class ShortestProcessingTimeStrategy:
    name = "shortest_processing_time"

    def order(self, tests: list[TestCase]) -> list[TestCase]:
        return sorted(tests, key=lambda test: (test.estimated_duration_seconds, test.name))


class FailureRateStrategy:
    name = "failure_rate"

    def order(self, tests: list[TestCase]) -> list[TestCase]:
        return sorted(tests, key=lambda test: (-test.historical_failure_rate, test.name))


@dataclass(frozen=True)
class CompositeWeights:
    failure_rate: float = 0.6
    duration: float = 0.2
    priority: float = 0.2


class CompositePriorityStrategy:
    name = "composite"

    def __init__(self, weights: CompositeWeights | None = None) -> None:
        self.weights = weights or CompositeWeights()

    def score(self, test: TestCase) -> float:
        duration_score = 1.0 / max(test.estimated_duration_seconds, 0.001)
        return (
            self.weights.failure_rate * test.historical_failure_rate
            + self.weights.duration * duration_score
            + self.weights.priority * test.priority
        )

    def order(self, tests: list[TestCase]) -> list[TestCase]:
        return sorted(tests, key=lambda test: (-self.score(test), test.name))


def strategy_by_name(name: str, seed: int = 1) -> SchedulerStrategy:
    strategies: dict[str, SchedulerStrategy] = {
        RandomStrategy.name: RandomStrategy(seed),
        ShortestProcessingTimeStrategy.name: ShortestProcessingTimeStrategy(),
        FailureRateStrategy.name: FailureRateStrategy(),
        CompositePriorityStrategy.name: CompositePriorityStrategy(),
    }
    if name not in strategies:
        raise ValueError(f"unknown scheduler strategy: {name}")
    return strategies[name]
