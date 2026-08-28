"""Level 3 - Functional testing.

Validates ECU behavior claims against the in-process vehicle:
  - normal vehicle behavior (start / drive / reverse / stop)
  - charging behavior (regen raises SOC)
  - motor commands (torque clamps, speed ramp)
  - battery conditions (low SOC, thermal faults)
  - invalid inputs (bogus gears, park+torque, unknown message ids)
"""

from __future__ import annotations

import pytest

from vehicle_validation.canbus.protocol import (
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_motor_status,
    make_vcu_command,
)
from vehicle_validation.ecu.motor import MotorConfig, MotorController
from vehicle_validation.ecu.vcu import VehicleControlUnit
from vehicle_validation.vehicle.controller import VehicleController


class TestNormalVehicleBehavior:
    def test_start_reaches_ready_with_no_fault(self, vehicle) -> None:
        snapshot = vehicle.start()

        assert snapshot.state == VehicleState.READY
        assert snapshot.gear == Gear.NEUTRAL
        assert snapshot.fault == FaultCode.NONE
        assert vehicle.can_trace  # frames flowed during startup

    def test_drive_accelerates_and_produces_torque(self, vehicle) -> None:
        vehicle.start()

        snapshot = vehicle.drive(100, Gear.DRIVE)

        assert snapshot.state == VehicleState.DRIVE
        assert snapshot.torque_nm > 0
        assert snapshot.speed_deci_kph > 0

    def test_reverse_applies_negative_torque(self, vehicle) -> None:
        vehicle.start()

        snapshot = vehicle.drive(80, Gear.REVERSE)

        assert snapshot.torque_nm < 0
        assert snapshot.gear == Gear.REVERSE

    def test_stop_returns_to_park_and_decelerates(self, vehicle) -> None:
        vehicle.start()
        vehicle.drive(150, Gear.DRIVE, 0)
        speed_before = vehicle.snapshot().speed_deci_kph
        assert speed_before > 0

        snapshot = vehicle.stop()

        assert snapshot.gear == Gear.PARK
        assert snapshot.torque_nm == 0
        assert snapshot.speed_deci_kph <= speed_before


class TestChargingBehavior:
    def test_regen_increases_soc(self, vehicle) -> None:
        vehicle.start()
        before = vehicle.snapshot().soc_percent

        snapshot = vehicle.drive(0, Gear.DRIVE, regen_percent=30)

        assert snapshot.soc_percent > before

    def test_motoring_decreases_soc(self, vehicle) -> None:
        vehicle.start()
        before = vehicle.snapshot().soc_percent

        for _ in range(20):
            vehicle.drive(150, Gear.DRIVE, 0)

        assert vehicle.snapshot().soc_percent < before

    def test_high_regen_is_clamped_to_max(self) -> None:
        vcu = VehicleControlUnit()
        vcu.receive(make_vcu_command(True, Gear.DRIVE, 50, regen_percent=100))

        assert vcu.state.regen_percent == vcu.config.max_regen_percent


class TestMotorCommands:
    def test_motor_torque_is_clamped_to_max(self) -> None:
        motor = MotorController()
        motor.command(True, 350, 7000)

        assert motor.state.torque_nm == motor.config.max_torque_nm

    def test_motor_speed_is_clamped_to_max(self) -> None:
        motor = MotorController()
        for _ in range(4):
            motor.command(True, 300, 1_000_000)

        assert motor.state.speed_rpm == motor.config.max_speed_rpm

    def test_motor_ignores_unknown_message_ids(self) -> None:
        motor = MotorController()
        frame = make_motor_status(VehicleState.DRIVE, 123, 45, 60, FaultCode.NONE)
        motor.receive(frame)

        assert motor.state.speed_rpm == 0  # MOTOR_STATUS != MOTOR_COMMAND, ignored

    def test_motor_disabled_command_zeros_torque(self) -> None:
        motor = MotorController()
        motor.command(False, 200, 7000)

        assert motor.state.enabled is False
        assert motor.state.torque_nm == 0


class TestBatteryConditions:
    def test_low_soc_triggers_fault(self) -> None:
        from vehicle_validation.ecu.bms import BatteryManagementSystem, BmsConfig

        vehicle = VehicleController(bms=BatteryManagementSystem(BmsConfig(low_soc_threshold=79.0)))
        vehicle.start()

        snapshot = vehicle.drive(3000, Gear.DRIVE)

        assert snapshot.soc_percent < 79
        assert snapshot.fault == FaultCode.LOW_SOC

    def test_drive_after_low_soc_disables(self) -> None:
        from vehicle_validation.ecu.bms import BatteryManagementSystem, BmsConfig

        vehicle = VehicleController(bms=BatteryManagementSystem(BmsConfig(low_soc_threshold=79.0)))
        vehicle.start()
        vehicle.drive(3000, Gear.DRIVE)

        snapshot = vehicle.drive(100, Gear.DRIVE)

        assert snapshot.state == VehicleState.FAULT
        assert snapshot.torque_nm == 0


class TestInvalidInputs:
    def test_park_with_torque_is_invalid_command(self) -> None:
        vcu = VehicleControlUnit()
        vcu.receive(make_vcu_command(True, Gear.PARK, 100))

        assert vcu.state.fault == FaultCode.INVALID_COMMAND

    def test_invalid_command_disables_motor_command(self) -> None:
        vcu = VehicleControlUnit()
        vcu.receive(make_vcu_command(True, Gear.PARK, 100))

        command = vcu.motor_command()

        assert bool(command.data[0]) is False
        assert int.from_bytes(command.data[1:3], "big", signed=True) == 0

    def test_neutral_blocks_torque(self) -> None:
        vcu = VehicleControlUnit()
        vcu.receive(make_vcu_command(True, Gear.NEUTRAL, 100))

        command = vcu.motor_command()

        assert int.from_bytes(command.data[1:3], "big", signed=True) == 0

    def test_oversized_torque_request_is_clamped_by_vcu(self) -> None:
        vcu = VehicleControlUnit()
        vcu.receive(make_vcu_command(True, Gear.DRIVE, 5000))

        command = vcu.motor_command()

        assert int.from_bytes(command.data[1:3], "big", signed=True) == vcu.config.max_torque_nm