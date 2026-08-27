"""Reproducible scheduler experiment helpers."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from vehicle_validation.scheduler.strategies import SchedulerStrategy, TestCase


@dataclass(frozen=True)
class ExperimentResult:
    strategy: str
    seed: int
    time_to_first_defect: float | None
    defects_within_budget: int
    total_duration: float
    ordered_tests: list[str]


def evaluate_order(
    strategy: SchedulerStrategy,
    tests: list[TestCase],
    seed: int,
    duration_budget_seconds: float,
) -> ExperimentResult:
    ordered = strategy.order(tests)
    elapsed = 0.0
    time_to_first_defect: float | None = None
    defects_within_budget = 0

    for test in ordered:
        elapsed += test.estimated_duration_seconds
        is_defect = test.historical_failure_rate >= 0.5
        if is_defect and time_to_first_defect is None:
            time_to_first_defect = elapsed
        if is_defect and elapsed <= duration_budget_seconds:
            defects_within_budget += 1

    return ExperimentResult(
        strategy=strategy.name,
        seed=seed,
        time_to_first_defect=time_to_first_defect,
        defects_within_budget=defects_within_budget,
        total_duration=sum(test.estimated_duration_seconds for test in ordered),
        ordered_tests=[test.name for test in ordered],
    )


def write_results_csv(results: list[ExperimentResult], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "strategy",
                "seed",
                "time_to_first_defect",
                "defects_within_budget",
                "total_duration",
                "ordered_tests",
            ],
        )
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row["ordered_tests"] = ",".join(result.ordered_tests)
            writer.writerow(row)
