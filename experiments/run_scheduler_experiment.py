#!/usr/bin/env python3
"""Run scheduler comparison experiments."""

from __future__ import annotations

from pathlib import Path

from vehicle_validation.scheduler.experiments import evaluate_order, write_results_csv
from vehicle_validation.scheduler.strategies import (
    CompositePriorityStrategy,
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
    TestCase,
)


def demo_tests() -> list[TestCase]:
    return [
        TestCase("startup", 0.5, 0.05, 0.2),
        TestCase("drive_nominal", 1.2, 0.15, 0.3),
        TestCase("low_soc_fault", 0.8, 0.75, 0.9),
        TestCase("motor_over_temp", 1.0, 0.65, 0.8),
        TestCase("reverse_drive", 0.7, 0.2, 0.4),
        TestCase("regen_soc", 0.9, 0.35, 0.6),
    ]


def main() -> None:
    tests = demo_tests()
    results = []
    for seed in range(1, 21):
        strategies = [
            RandomStrategy(seed),
            ShortestProcessingTimeStrategy(),
            FailureRateStrategy(),
            CompositePriorityStrategy(),
        ]
        for strategy in strategies:
            results.append(evaluate_order(strategy, tests, seed, duration_budget_seconds=3.0))

    output = Path("experiments/results/scheduler_comparison.csv")
    write_results_csv(results, output)
    print(f"wrote {len(results)} rows to {output}")


if __name__ == "__main__":
    main()
