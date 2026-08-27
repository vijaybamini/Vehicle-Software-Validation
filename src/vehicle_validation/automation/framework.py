"""Reusable scenario runner for vehicle validation tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vehicle_validation.automation.results import StepResult, Stopwatch, TestResult
from vehicle_validation.vehicle.controller import VehicleController, VehicleSnapshot


StepAction = Callable[[VehicleController], VehicleSnapshot]
StepAssertion = Callable[[VehicleSnapshot], None]


@dataclass(frozen=True)
class ScenarioStep:
    name: str
    action: StepAction
    assertion: StepAssertion | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    steps: tuple[ScenarioStep, ...]


class ScenarioRunner:
    def __init__(self, vehicle_factory: Callable[[], VehicleController] = VehicleController) -> None:
        self.vehicle_factory = vehicle_factory

    def run(self, scenario: Scenario) -> TestResult:
        vehicle = self.vehicle_factory()
        total_watch = Stopwatch()
        step_results: list[StepResult] = []

        for step in scenario.steps:
            step_watch = Stopwatch()
            try:
                snapshot = step.action(vehicle)
                if step.assertion is not None:
                    step.assertion(snapshot)
            except AssertionError as exc:
                step_results.append(StepResult(step.name, False, step_watch.elapsed(), str(exc)))
                return TestResult(scenario.name, False, total_watch.elapsed(), step_results, str(exc))

            step_results.append(StepResult(step.name, True, step_watch.elapsed()))

        return TestResult(scenario.name, True, total_watch.elapsed(), step_results)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
