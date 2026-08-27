"""Closed-loop validation run execution."""

from __future__ import annotations

from uuid import uuid4

from vehicle_validation.automation.catalog import ScenarioDefinition, default_delay_fault_targets, scenario_catalog
from vehicle_validation.automation.faults import MessageDelayInjector
from vehicle_validation.automation.framework import ScenarioRunner
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.automation.results import TestRun
from vehicle_validation.database.history import HistoryStore
from vehicle_validation.scheduler.strategies import TestCase, strategy_by_name
from vehicle_validation.vehicle.controller import VehicleController


class ValidationExecutor:
    def __init__(
        self,
        history: HistoryStore,
        logger: StructuredLogger,
    ) -> None:
        self.history = history
        self.logger = logger

    def run(
        self,
        strategy_name: str = "composite",
        seed: int = 1,
        enable_delay_fault: bool = False,
        run_id: str | None = None,
    ) -> TestRun:
        definitions = self._ordered_definitions(strategy_name, seed)
        test_run = TestRun.create(
            run_id or str(uuid4()),
            {
                "strategy": strategy_name,
                "seed": str(seed),
                "delay_fault": str(enable_delay_fault).lower(),
            },
        )

        for definition in definitions:
            runner = ScenarioRunner(lambda: self._vehicle(enable_delay_fault, seed))
            result = runner.run(definition.scenario)
            test_run.add(result)
            if not result.passed and result.diagnostics is not None:
                self.logger.write("diagnostic.failure", result.diagnostics)

        self.history.save_run(test_run)
        self.logger.write("run.completed", test_run.to_dict())
        return test_run

    def tests_with_history(self) -> list[TestCase]:
        historical = self.history.test_profiles()
        enriched = []
        for test in self._test_cases_by_name().values():
            profile = historical.get(test.name, {})
            enriched.append(
                TestCase(
                    name=test.name,
                    estimated_duration_seconds=float(
                        profile.get("average_duration_seconds", test.estimated_duration_seconds)
                    ),
                    historical_failure_rate=float(
                        profile.get("failure_rate", test.historical_failure_rate)
                    ),
                    priority=test.priority,
                )
            )
        return enriched

    def _ordered_definitions(self, strategy_name: str, seed: int) -> list[ScenarioDefinition]:
        strategy = strategy_by_name(strategy_name, seed)
        ordered_cases = strategy.order(self.tests_with_history())
        definitions = {definition.test_case.name: definition for definition in scenario_catalog()}
        return [definitions[test.name] for test in ordered_cases]

    def _test_cases_by_name(self) -> dict[str, TestCase]:
        return {definition.test_case.name: definition.test_case for definition in scenario_catalog()}

    def _vehicle(self, enable_delay_fault: bool, seed: int) -> VehicleController:
        if not enable_delay_fault:
            return VehicleController()
        injector = MessageDelayInjector(default_delay_fault_targets(), delay_ticks=3, probability=1.0, seed=seed)
        return VehicleController(fault_injector=injector)
