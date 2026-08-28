"""Level 7 - Scheduler.

Validates the scheduler claims:
  - random ordering (reproducible with seeds)
  - SPT ordering (shortest estimated duration first)
  - failure-rate ordering (highest historical failure first)
  - composite strategy weights
  - historical data actually influences ordering
  - reproducibility with seeds
"""

from __future__ import annotations

import pytest

from vehicle_validation.automation.executor import ValidationExecutor
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.automation.results import TestResult, TestRun
from vehicle_validation.database.history import HistoryStore
from vehicle_validation.scheduler.strategies import (
    CompositePriorityStrategy,
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
    TestCase,
    strategy_by_name,
)
from tests.validation.conftest import build_components

DRIVE = "drive_command_produces_speed_and_torque"


def _cases() -> list[TestCase]:
    return [
        TestCase("fast", 0.1, 0.0, 0.0),
        TestCase("slow", 5.0, 0.9, 0.0),
        TestCase("mid", 1.0, 0.5, 0.5),
        TestCase("fast2", 0.1, 1.0, 0.0),
        TestCase("priority", 2.0, 0.1, 1.0),
    ]


def _names(cases: list[TestCase]) -> list[str]:
    return [case.name for case in cases]


def test_spt_orders_by_shortest_estimated_duration_first() -> None:
    ordered = _names(ShortestProcessingTimeStrategy().order(_cases()))

    assert ordered[0] == "fast"
    assert ordered[1] == "fast2"
    assert ordered[-1] == "slow"
    durations = [case.estimated_duration_seconds for case in ShortestProcessingTimeStrategy().order(_cases())]
    assert durations == sorted(durations)


def test_failure_rate_orders_by_highest_first() -> None:
    ordered = _names(FailureRateStrategy().order(_cases()))

    assert ordered[0] == "fast2"
    assert ordered[1] == "slow"
    assert ordered[-1] == "fast"
    rates = [case.historical_failure_rate for case in FailureRateStrategy().order(_cases())]
    assert rates == sorted(rates, reverse=True)


def test_composite_strategy_orders_by_weighted_score() -> None:
    strategy = CompositePriorityStrategy()

    ordered = _names(strategy.order(_cases()))

    assert ordered == ["fast2", "fast", "mid", "slow", "priority"]
    scores = [strategy.score(case) for case in strategy.order(_cases())]
    assert scores == sorted(scores, reverse=True)


def test_composite_emphasizes_historical_failure_rate() -> None:
    flaky = TestCase("flaky", 1.0, 0.95, 0.0)
    reliable = TestCase("reliable", 0.5, 0.0, 0.0)

    ordered = _names(CompositePriorityStrategy().order([flaky, reliable]))

    assert ordered[0] == "flaky"


def test_random_strategy_is_reproducible_with_seed() -> None:
    first = _names(strategy_by_name("random", 42).order(_cases()))
    second = _names(strategy_by_name("random", 42).order(_cases()))
    different = _names(strategy_by_name("random", 43).order(_cases()))

    assert first == second
    assert first != different


def test_random_variants_cover_different_orderings() -> None:
    orderings = {tuple(_names(RandomStrategy(seed).order(_cases()))) for seed in range(20)}

    assert len(orderings) > 1


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError):
        strategy_by_name("not-a-strategy")


def test_history_feeds_scheduler_ordering(components) -> None:
    history, logger, executor = components
    failing = TestRun.create("r1", {"strategy": "composite"})
    failing.add(TestResult(DRIVE, False, 1.5))
    history.save_run(failing)

    tests = executor.tests_with_history()
    by_name = {test.name: test for test in tests}
    assert by_name[DRIVE].historical_failure_rate == pytest.approx(1.0)

    failure_ordered = _names(FailureRateStrategy().order(tests))
    assert failure_ordered[0] == DRIVE

    composite_ordered = _names(CompositePriorityStrategy().order(tests))
    assert composite_ordered[0] == DRIVE

    executor_ordered = executor._ordered_definitions("failure_rate", seed=1)
    assert executor_ordered[0].test_case.name == DRIVE


def test_spt_reacts_to_historical_durations(tmp_path) -> None:
    history, logger, executor = build_components(tmp_path)
    slow_run = TestRun.create("slow-history")
    slow_run.add(TestResult(DRIVE, True, 9.0))
    history.save_run(slow_run)

    tests = executor.tests_with_history()
    ordered = _names(ShortestProcessingTimeStrategy().order(tests))

    assert ordered[-1] == DRIVE  # now the longest by historical average