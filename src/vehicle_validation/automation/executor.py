"""Closed-loop validation run execution."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from vehicle_validation.automation.catalog import ScenarioDefinition, default_delay_fault_targets, scenario_catalog
from vehicle_validation.automation.faults import MessageDelayInjector
from vehicle_validation.automation.framework import ScenarioRunner
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.automation.results import TestResult, TestRun
from vehicle_validation.canbus.transport import CanTransportConfig, PythonCanTransport
from vehicle_validation.database.history import HistoryStore
from vehicle_validation.ecu.supervisor import EcuSupervisor, can_channel_available
from vehicle_validation.scheduler.strategies import TestCase, strategy_by_name
from vehicle_validation.vehicle.bus_controller import BusVehicleController
from vehicle_validation.vehicle.controller import VehicleController

ProgressCallback = Callable[[dict], None]

IN_PROCESS_MODE = "in-process-fallback"
SOCKETCAN_MODE = "socketcan-processes"


class ValidationExecutor:
    def __init__(
        self,
        history: HistoryStore,
        logger: StructuredLogger,
        *,
        channel: str | None = None,
        supervisor_factory: Callable[[CanTransportConfig], EcuSupervisor] = EcuSupervisor,
        transport_factory: Callable[[CanTransportConfig], PythonCanTransport] = PythonCanTransport,
    ) -> None:
        self.history = history
        self.logger = logger
        self.channel = channel
        self.supervisor_factory = supervisor_factory
        self.transport_factory = transport_factory

    def run(
        self,
        strategy_name: str = "composite",
        seed: int = 1,
        enable_delay_fault: bool = False,
        run_id: str | None = None,
        on_event: ProgressCallback | None = None,
    ) -> TestRun:
        if self._socketcan_mode(enable_delay_fault):
            try:
                return self._run_on_bus(strategy_name, seed, run_id, on_event)
            except Exception as exc:  # noqa: BLE001 - deliberate fallback
                self.logger.write("run.fallback", {"channel": self.channel, "reason": str(exc)})
        return self._run_in_process(strategy_name, seed, enable_delay_fault, run_id, on_event)

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

    def _run_in_process(
        self,
        strategy_name: str,
        seed: int,
        enable_delay_fault: bool,
        run_id: str | None,
        on_event: ProgressCallback | None,
    ) -> TestRun:
        metadata = self._metadata(IN_PROCESS_MODE, strategy_name, seed, enable_delay_fault)
        test_run = TestRun.create(run_id or str(uuid4()), metadata)
        definitions = self._ordered_definitions(strategy_name, seed)
        self._broadcast(on_event, "run.started", self._start_payload(test_run, definitions, metadata))
        try:
            self._run_scenarios(
                test_run,
                definitions,
                lambda: self._vehicle(enable_delay_fault, seed),
                on_event,
            )
        finally:
            self.history.save_run(test_run)
        self.logger.write("run.completed", test_run.to_dict())
        self._broadcast(on_event, "run.completed", self._completion_payload(test_run))
        return test_run

    def _run_on_bus(
        self,
        strategy_name: str,
        seed: int,
        run_id: str | None,
        on_event: ProgressCallback | None,
    ) -> TestRun:
        definitions = [
            definition for definition in self._ordered_definitions(strategy_name, seed) if definition.bus_safe
        ]
        metadata = self._metadata(SOCKETCAN_MODE, strategy_name, seed, False)
        test_run = TestRun.create(run_id or str(uuid4()), metadata)
        self._broadcast(on_event, "run.started", self._start_payload(test_run, definitions, metadata))

        supervisor = self.supervisor_factory(CanTransportConfig(channel=self.channel or "vcan0"))
        supervisor.start()
        try:
            with self.transport_factory(CanTransportConfig(channel=self.channel or "vcan0")) as transport:
                self._run_scenarios(
                    test_run,
                    definitions,
                    lambda: BusVehicleController(transport),
                    on_event,
                )
        finally:
            supervisor.stop()

        self.history.save_run(test_run)
        self.logger.write("run.completed", test_run.to_dict())
        self._broadcast(on_event, "run.completed", self._completion_payload(test_run))
        return test_run

    def _run_scenarios(
        self,
        test_run: TestRun,
        definitions: list[ScenarioDefinition],
        vehicle_factory: Callable[[], object],
        on_event: ProgressCallback | None,
    ) -> None:
        total = len(definitions)
        for index, definition in enumerate(definitions, start=1):
            self._broadcast(
                on_event,
                "test.started",
                {
                    "run_id": test_run.run_id,
                    "name": definition.test_case.name,
                    "index": index,
                    "total": total,
                },
            )
            runner = ScenarioRunner(vehicle_factory)
            result = runner.run(definition.scenario)
            test_run.add(result)
            self._broadcast_result(on_event, test_run, result)
            if not result.passed and result.diagnostics is not None:
                self.logger.write("diagnostic.failure", result.diagnostics)

    def _broadcast_result(
        self,
        on_event: ProgressCallback | None,
        test_run: TestRun,
        result: TestResult,
    ) -> None:
        event = "test.passed" if result.passed else "test.failed"
        payload = {
            "run_id": test_run.run_id,
            "name": result.name,
            "duration_seconds": result.duration_seconds,
        }
        if not result.passed:
            payload["failure_reason"] = result.failure_reason
        self._broadcast(on_event, event, payload)

    def _ordered_definitions(self, strategy_name: str, seed: int) -> list[ScenarioDefinition]:
        strategy = strategy_by_name(strategy_name, seed)
        ordered_cases = strategy.order(self.tests_with_history())
        definitions = {definition.test_case.name: definition for definition in scenario_catalog()}
        return [definitions[test.name] for test in ordered_cases]

    def _test_cases_by_name(self) -> dict[str, TestCase]:
        return {definition.test_case.name: definition.test_case for definition in scenario_catalog()}

    @staticmethod
    def _broadcast(on_event: ProgressCallback | None, event: str, payload: dict) -> None:
        if on_event is not None:
            on_event({"event": event, "payload": payload})

    @staticmethod
    def _metadata(mode: str, strategy_name: str, seed: int, enable_delay_fault: bool) -> dict[str, str]:
        return {
            "strategy": strategy_name,
            "seed": str(seed),
            "delay_fault": str(enable_delay_fault).lower(),
            "mode": mode,
        }

    @staticmethod
    def _start_payload(test_run: TestRun, definitions: list[ScenarioDefinition], metadata: dict[str, str]) -> dict:
        return {
            "run_id": test_run.run_id,
            "strategy": metadata["strategy"],
            "seed": metadata["seed"],
            "mode": metadata["mode"],
            "total": len(definitions),
        }

    @staticmethod
    def _completion_payload(test_run: TestRun) -> dict:
        return {
            "run_id": test_run.run_id,
            "summary": test_run.to_dict()["summary"],
            "mode": test_run.metadata.get("mode", IN_PROCESS_MODE),
        }

    def _socketcan_mode(self, enable_delay_fault: bool) -> bool:
        if self.channel is None or enable_delay_fault:
            return False
        return can_channel_available(self.channel)

    def _vehicle(self, enable_delay_fault: bool, seed: int) -> VehicleController:
        if not enable_delay_fault:
            return VehicleController()
        injector = MessageDelayInjector(default_delay_fault_targets(), delay_ticks=3, probability=1.0, seed=seed)
        return VehicleController(fault_injector=injector)