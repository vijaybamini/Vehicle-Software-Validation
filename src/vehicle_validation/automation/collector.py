"""Collect scenario results into structured test runs."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from vehicle_validation.automation.framework import Scenario, ScenarioRunner
from vehicle_validation.automation.results import TestRun


class ResultCollector:
    def __init__(self, runner: ScenarioRunner | None = None) -> None:
        self.runner = runner or ScenarioRunner()

    def run_scenarios(
        self,
        scenarios: Iterable[Scenario],
        run_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TestRun:
        test_run = TestRun.create(run_id or str(uuid4()), metadata)
        for scenario in scenarios:
            test_run.add(self.runner.run(scenario))
        return test_run
