"""Level 2 - pytest automation framework.

Validates the automation harness claims:
  - test discovery from the scenario catalog
  - fixtures providing reusable ECU objects
  - test execution with pass/fail handling and step durations
  - reusable ECU interfaces (same scenarios over in-process and bus controllers)
  - cleanup after tests (supervisor stopped, transport closed, re-runnable)
"""

from __future__ import annotations

from vehicle_validation.automation.catalog import scenario_catalog
from vehicle_validation.automation.executor import IN_PROCESS_MODE, ValidationExecutor
from vehicle_validation.automation.framework import Scenario, ScenarioStep, ScenarioRunner, require
from vehicle_validation.canbus.protocol import VehicleState
from vehicle_validation.vehicle.bus_controller import BusVehicleController
from tests.unit.test_bus_vehicle_controller import FakeEcuTransport


def test_catalog_discovery_has_all_resume_scenarios() -> None:
    definitions = scenario_catalog()

    assert len(definitions) == 5
    names = {definition.test_case.name for definition in definitions}
    assert names == {
        "startup_reaches_ready_state",
        "drive_command_produces_speed_and_torque",
        "reverse_command_produces_negative_torque",
        "low_soc_forces_vehicle_fault",
        "motor_over_temperature_reaches_fault",
    }
    for definition in definitions:
        assert definition.test_case.estimated_duration_seconds > 0
        assert definition.test_case.priority >= 0
        assert definition.scenario.steps


def test_fixtures_provide_working_ecu_objects(bms, motor, vcu, vehicle) -> None:
    assert bms.publish()
    assert motor.publish().arbitration_id == motor.publish().arbitration_id
    assert vcu.publish() is not None
    assert vehicle.start().state == VehicleState.READY


def test_runner_executes_catalog_scenarios_and_records_durations() -> None:
    runner = ScenarioRunner()

    for definition in scenario_catalog():
        result = runner.run(definition.scenario)

        assert result.name == definition.test_case.name
        assert result.passed is True
        assert result.duration_seconds > 0
        assert result.steps
        for step in result.steps:
            assert step.passed is True
            assert step.duration_seconds >= 0


def test_pass_fail_handling_records_failure_reason_and_diagnostic() -> None:
    from vehicle_validation.canbus.protocol import Gear

    scenario = Scenario(
        "failing_scenario",
        (
            ScenarioStep(
                "start",
                lambda vehicle: vehicle.start(),
                lambda snapshot: require(snapshot.state == VehicleState.READY, "ready expected"),
            ),
            ScenarioStep(
                "drive",
                lambda vehicle: vehicle.drive(10, Gear.DRIVE),
                lambda snapshot: require(snapshot.state == VehicleState.FAULT, "fault expected"),
            ),
        ),
    )
    result = ScenarioRunner().run(scenario)

    assert result.passed is False
    assert result.failure_reason == "fault expected"
    assert result.diagnostics is not None
    assert "fault" in result.diagnostics
    assert all(step.passed for step in result.steps[:-1])


def test_same_scenarios_run_over_in_process_and_bus_interfaces() -> None:
    """The catalog scenarios are the reusable ECU interface:
    in-process and bus drivers both pass the same validated expectations."""
    in_process = {definition.test_case.name: definition for definition in scenario_catalog()}
    bus_safe = {name: definition for name, definition in in_process.items() if definition.bus_safe}

    for name, definition in bus_safe.items():
        in_process_result = ScenarioRunner().run(definition.scenario)
        bus_result = ScenarioRunner(lambda: BusVehicleController(FakeEcuTransport())).run(definition.scenario)

        assert in_process_result.passed is True, name
        assert bus_result.passed is True, name
        assert bus_result.name == in_process_result.name


def test_cleanup_after_bus_run(tmp_path, monkeypatch) -> None:
    from tests.validation.conftest import FakeSupervisor, build_components

    import vehicle_validation.automation.executor as executor_module

    class TrackingTransport(FakeEcuTransport):
        def close(self) -> None:  # type: ignore[override]
            self.closed = True

        closed = False

    monkeypatch.setattr(executor_module, "can_channel_available", lambda channel: True)
    history, logger, _ = build_components(tmp_path)
    supervisor = FakeSupervisor()
    transport = TrackingTransport()
    executor = ValidationExecutor(
        history,
        logger,
        channel="vcan0",
        supervisor_factory=lambda config: supervisor,
        transport_factory=lambda config: transport,
    )

    result = executor.run(strategy_name="composite", seed=1)

    assert result.metadata["mode"] == "socketcan-processes"
    assert supervisor.started and supervisor.stopped
    assert transport.closed is True

    re_run = executor.run(strategy_name="composite", seed=2, enable_delay_fault=True)
    assert re_run.metadata["mode"] == IN_PROCESS_MODE
    assert history.statistics()["runs"] == 2