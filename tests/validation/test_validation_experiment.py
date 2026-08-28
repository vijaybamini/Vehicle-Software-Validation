"""Level 8 - Experiment.

Validates the experiment / scheduler-comparison claims:
  - repeated evaluation across seeds is stable and reproducible
  - time-to-first-defect is measured correctly
  - comparison between strategies produces consistent raw data
  - raw CSV data is correct and loadable into statistics (pandas)

NOTE: graph plotting (matplotlib) is part of the spec but not implemented as a
script yet; this level validates the raw-data -> statistics path it feeds.
"""

from __future__ import annotations

import csv

import pytest

from vehicle_validation.scheduler.experiments import ExperimentResult, evaluate_order, write_results_csv
from vehicle_validation.scheduler.strategies import (
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
    TestCase,
    strategy_by_name,
)

STRATEGY_NAMES = ["composite", "failure_rate", "random", "shortest_processing_time"]


def _defect_tests() -> list[TestCase]:
    return [
        TestCase("a", 0.5, 0.0),
        TestCase("b", 0.5, 1.0),
        TestCase("c", 1.0, 1.0),
    ]


def test_time_to_first_defect_measured_correctly() -> None:
    result = evaluate_order(ShortestProcessingTimeStrategy(), _defect_tests(), seed=1, duration_budget_seconds=3.0)

    assert result.strategy == "shortest_processing_time"
    assert result.ordered_tests == ["a", "b", "c"]
    assert result.time_to_first_defect == pytest.approx(1.0)  # b fails at elapsed 1.0
    assert result.defects_within_budget == 2
    assert result.total_duration == pytest.approx(2.0)


def test_defects_outside_budget_are_not_counted() -> None:
    result = evaluate_order(ShortestProcessingTimeStrategy(), _defect_tests(), seed=1, duration_budget_seconds=1.5)

    assert result.defects_within_budget == 1  # b at 1.0 only; c at 2.0 > 1.5


def test_clean_dataset_has_no_first_defect() -> None:
    clean = [TestCase("a", 0.5, 0.0), TestCase("b", 0.5, 0.0)]
    result = evaluate_order(ShortestProcessingTimeStrategy(), clean, seed=1, duration_budget_seconds=3.0)

    assert result.time_to_first_defect is None
    assert result.defects_within_budget == 0


def test_failure_rate_strategy_places_defects_first() -> None:
    result = evaluate_order(FailureRateStrategy(), _defect_tests(), seed=1, duration_budget_seconds=3.0)

    assert result.time_to_first_defect == pytest.approx(0.5)
    assert result.ordered_tests[0] == "b"


def test_repeated_evaluation_is_reproducible_for_a_seed() -> None:
    strategy = strategy_by_name("random", 5)
    tests = [TestCase(f"t{i}", 0.5, 0.0) for i in range(6)]

    first = evaluate_order(strategy, tests, seed=5, duration_budget_seconds=3.0)
    second = evaluate_order(strategy, tests, seed=5, duration_budget_seconds=3.0)

    assert first.ordered_tests == second.ordered_tests
    assert first == second


def test_total_duration_is_order_independent_across_strategies() -> None:
    tests = [TestCase(f"t{i}", 1.0, 0.2) for i in range(5)]
    expected_total = 5.0

    for name in STRATEGY_NAMES:
        result = evaluate_order(strategy_by_name(name, 3), tests, seed=3, duration_budget_seconds=3.0)
        assert result.total_duration == pytest.approx(expected_total)
        assert len(result.ordered_tests) == len(tests)


def test_comparison_campaign_produces_valid_results_for_all_seeds() -> None:
    tests = _defect_tests()

    for seed in range(20):
        for name in STRATEGY_NAMES:
            result = evaluate_order(strategy_by_name(name, seed), tests, seed=seed, duration_budget_seconds=3.0)
            assert isinstance(result, ExperimentResult)
            assert result.seed == seed
            assert isinstance(result.defects_within_budget, int)
            assert set(result.ordered_tests) == {"a", "b", "c"}


def test_raw_data_round_trips_through_csv(tmp_path) -> None:
    tests = _defect_tests()
    results = [
        evaluate_order(strategy_by_name(name, seed), tests, seed=seed, duration_budget_seconds=3.0)
        for seed in range(20)
        for name in STRATEGY_NAMES
    ]
    path = tmp_path / "comparison.csv"

    write_results_csv(results, path)
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))

    assert len(rows) == 20 * len(STRATEGY_NAMES)
    header = set(rows[0].keys())
    assert {"strategy", "seed", "time_to_first_defect", "defects_within_budget", "total_duration", "ordered_tests"} == header

    for result in results:
        matches = [
            row
            for row in rows
            if row["strategy"] == result.strategy and int(row["seed"]) == result.seed
        ]
        assert len(matches) == 1
        row = matches[0]
        assert row["defects_within_budget"] == str(result.defects_within_budget)
        assert row["ordered_tests"] == ",".join(result.ordered_tests)


def test_raw_data_loads_into_pandas_statistics(tmp_path) -> None:
    pd = pytest.importorskip("pandas")
    tests = _defect_tests()
    results = [
        evaluate_order(strategy_by_name(name, seed), tests, seed=seed, duration_budget_seconds=3.0)
        for seed in range(20)
        for name in STRATEGY_NAMES
    ]
    path = tmp_path / "comparison.csv"
    write_results_csv(results, path)

    frame = pd.read_csv(path)

    assert set(frame.columns) == {
        "strategy",
        "seed",
        "time_to_first_defect",
        "defects_within_budget",
        "total_duration",
        "ordered_tests",
    }
    assert len(frame) == 80
    means = frame.groupby("strategy")["defects_within_budget"].mean()
    assert list(means.index) == ["composite", "failure_rate", "random", "shortest_processing_time"]
    assert (means > 0).all()