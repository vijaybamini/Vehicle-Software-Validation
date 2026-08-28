"""Level 4 - Fault injection.

Validates the fault-injection claims:
  - message delay/loss is truly injected (held, released, or dropped)
  - the injected fault changes ECU-visible behavior
  - the ECU detects/handles it (and documents what is NOT handled)
  - pytest reports the resulting behavior back into results/history
"""

from __future__ import annotations

import pytest

from vehicle_validation.automation.catalog import default_delay_fault_targets
from vehicle_validation.automation.faults import MessageDelayInjector
from vehicle_validation.canbus.protocol import (
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_bms_status,
    make_motor_status,
)
from vehicle_validation.ecu.vcu import VehicleControlUnit
from vehicle_validation.vehicle.controller import VehicleController


def _motor_frame(speed_rpm: int = 100, torque_nm: int = 50) -> "object":
    return make_motor_status(VehicleState.DRIVE, speed_rpm, torque_nm, 35, FaultCode.NONE)


def test_delay_injection_holds_then_releases_target_frame() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=3, probability=1.0)

    assert injector.inject(_motor_frame()) == []
    assert injector.pending_count == 1

    released: list = []
    for _ in range(3):
        released.extend(injector.advance())

    assert released == [_motor_frame()]
    assert injector.pending_count == 0


def test_non_target_frames_pass_through_immediately() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=3)
    frame = make_bms_status(VehicleState.READY, 80, 99, 3600, 0, FaultCode.NONE)

    delivered = injector.inject(frame)

    assert delivered == [frame]
    assert injector.pending_count == 0


def test_probability_zero_passes_everything_through() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=3, probability=0.0)

    for _ in range(5):
        assert injector.inject(_motor_frame()) == [_motor_frame()]
    assert injector.pending_count == 0


def test_injector_is_deterministic_for_a_given_seed() -> None:
    frames = [_motor_frame(speed_rpm=i) for i in range(12)]
    first = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=2, probability=0.5, seed=7)
    second = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=2, probability=0.5, seed=7)

    first_decisions = [len(first.inject(frame)) == 0 for frame in frames]
    second_decisions = [len(second.inject(frame)) == 0 for frame in frames]

    assert first_decisions == second_decisions
    assert any(first_decisions) and not all(first_decisions)


def test_injector_validation_of_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=-1)
    with pytest.raises(ValueError):
        MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=1, probability=1.5)


def test_delayed_motor_status_changes_driver_visible_behavior() -> None:
    clean = VehicleController()
    clean.start()
    clean_snapshot = clean.drive(100, Gear.DRIVE)

    injected = VehicleController(
        fault_injector=MessageDelayInjector(default_delay_fault_targets(), delay_ticks=3, probability=1.0, seed=1)
    )
    injected.start()
    injected_snapshot = injected.drive(100, Gear.DRIVE)

    assert clean_snapshot.torque_nm == 100
    assert injected_snapshot.torque_nm != clean_snapshot.torque_nm
    assert injected.fault_injector.pending_count >= 1


def test_executor_fault_run_differs_and_reports_failures(components) -> None:
    history, logger, executor = components

    clean = executor.run(strategy_name="composite", seed=1)
    faulted = executor.run(strategy_name="composite", seed=1, enable_delay_fault=True)

    assert clean.passed == len(clean.results)
    assert faulted.metadata["delay_fault"] == "true"
    assert faulted.passed < len(faulted.results)
    for result in faulted.results:
        if not result.passed:
            assert result.failure_reason
            assert result.diagnostics is not None

    drive_profile = history.test_profiles().get("drive_command_produces_speed_and_torque", {})
    assert drive_profile.get("failure_rate", 0) > 0


def test_fault_runs_are_repeatable_without_corruption(components) -> None:
    history, logger, executor = components

    for seed in range(4):
        executor.run(strategy_name="composite", seed=seed, enable_delay_fault=True)

    assert history.statistics()["runs"] == 4


def test_vcu_detects_motor_status_timeout_when_frames_withheld() -> None:
    vcu = VehicleControlUnit()
    vcu.receive(make_vcu_status_command())
    vcu.receive(make_motor_status(VehicleState.DRIVE, 500, 50, 35, FaultCode.NONE))

    for _ in range(10):
        status = vcu.publish()

    assert status.data[0] == VehicleState.FAULT
    assert vcu.state.fault == FaultCode.COMMUNICATION_TIMEOUT


def test_motor_comms_loss_is_detected_as_communication_timeout() -> None:
    vcu = VehicleControlUnit()
    vcu.receive(make_vcu_status_command())
    vcu.receive(make_motor_status(VehicleState.DRIVE, 500, 50, 35, FaultCode.NONE))

    for _ in range(10):
        vcu.publish()

    assert vcu.state.fault == FaultCode.COMMUNICATION_TIMEOUT


def make_vcu_status_command():
    from vehicle_validation.canbus.protocol import make_vcu_command

    return make_vcu_command(True, Gear.DRIVE, 50)
