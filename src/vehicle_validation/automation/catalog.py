"""Executable validation scenario catalog."""

from __future__ import annotations

from dataclasses import dataclass

from vehicle_validation.automation.framework import Scenario, ScenarioStep, require
from vehicle_validation.canbus.protocol import FaultCode, Gear, MessageId, VehicleState
from vehicle_validation.ecu.bms import BatteryManagementSystem, BmsConfig
from vehicle_validation.ecu.motor import MotorConfig, MotorController
from vehicle_validation.scheduler.strategies import TestCase
from vehicle_validation.vehicle.controller import VehicleController, VehicleSnapshot


@dataclass(frozen=True)
class ScenarioDefinition:
    test_case: TestCase
    scenario: Scenario
    bus_safe: bool = False


def scenario_catalog() -> list[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            TestCase("startup_reaches_ready_state", 0.5, 0.0, 0.2),
            Scenario(
                "startup_reaches_ready_state",
                (
                    ScenarioStep(
                        "start",
                        lambda vehicle: vehicle.start(),
                        lambda snapshot: require(
                            snapshot.state == VehicleState.READY,
                            f"expected ready, got {snapshot.state.name.lower()}",
                        ),
                    ),
                ),
            ),
            bus_safe=True,
        ),
        ScenarioDefinition(
            TestCase("drive_command_produces_speed_and_torque", 1.2, 0.0, 0.3),
            Scenario(
                "drive_command_produces_speed_and_torque",
                (
                    ScenarioStep("start", lambda vehicle: vehicle.start()),
                    ScenarioStep(
                        "drive",
                        lambda vehicle: vehicle.drive(100, Gear.DRIVE),
                        _expect_drive_torque,
                    ),
                ),
            ),
            bus_safe=True,
        ),
        ScenarioDefinition(
            TestCase("reverse_command_produces_negative_torque", 0.7, 0.0, 0.4),
            Scenario(
                "reverse_command_produces_negative_torque",
                (
                    ScenarioStep("start", lambda vehicle: vehicle.start()),
                    ScenarioStep(
                        "reverse",
                        lambda vehicle: vehicle.drive(80, Gear.REVERSE),
                        lambda snapshot: require(snapshot.torque_nm == -80, f"expected -80 Nm, got {snapshot.torque_nm}"),
                    ),
                ),
            ),
            bus_safe=True,
        ),
        ScenarioDefinition(
            TestCase("low_soc_forces_vehicle_fault", 0.8, 0.0, 0.9),
            Scenario(
                "low_soc_forces_vehicle_fault",
                (
                    ScenarioStep("start", lambda vehicle: vehicle.start()),
                    ScenarioStep(
                        "low_soc",
                        lambda vehicle: _drive_low_soc_vehicle(vehicle),
                        lambda snapshot: require(snapshot.fault == FaultCode.LOW_SOC, f"expected low_soc, got {snapshot.fault.name.lower()}"),
                    ),
                ),
            ),
        ),
        ScenarioDefinition(
            TestCase("motor_over_temperature_reaches_fault", 1.0, 0.0, 0.8),
            Scenario(
                "motor_over_temperature_reaches_fault",
                (
                    ScenarioStep("start", lambda vehicle: vehicle.start()),
                    ScenarioStep(
                        "over_temperature",
                        lambda vehicle: _drive_hot_motor_vehicle(vehicle),
                        lambda snapshot: require(
                            snapshot.fault == FaultCode.OVER_TEMPERATURE,
                            f"expected over_temperature, got {snapshot.fault.name.lower()}",
                        ),
                    ),
                ),
            ),
        ),
    ]


def catalog_test_cases() -> list[TestCase]:
    return [definition.test_case for definition in scenario_catalog()]


def _expect_drive_torque(snapshot: VehicleSnapshot) -> None:
    require(snapshot.state == VehicleState.DRIVE, f"expected drive, got {snapshot.state.name.lower()}")
    require(snapshot.speed_deci_kph > 0, f"expected speed > 0, got {snapshot.speed_deci_kph}")
    require(snapshot.torque_nm == 100, f"expected 100 Nm, got {snapshot.torque_nm}")


def _drive_low_soc_vehicle(vehicle: VehicleController) -> VehicleSnapshot:
    vehicle.bms = BatteryManagementSystem(BmsConfig(low_soc_threshold=79.0))
    return vehicle.drive(3000, Gear.DRIVE)


def _drive_hot_motor_vehicle(vehicle: VehicleController) -> VehicleSnapshot:
    vehicle.motor = MotorController(MotorConfig(over_temperature_celsius=36))
    vehicle.motor.state.temperature_celsius = 36
    return vehicle.drive(200, Gear.DRIVE)


def default_delay_fault_targets() -> set[int]:
    return {MessageId.MOTOR_STATUS}
