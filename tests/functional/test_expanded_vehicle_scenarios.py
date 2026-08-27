from time import perf_counter

from vehicle_validation.canbus.protocol import FaultCode, Gear, VehicleState
from vehicle_validation.ecu.motor import MotorConfig, MotorController
from vehicle_validation.vehicle.controller import VehicleController


def test_neutral_gear_blocks_drive_torque(vehicle: VehicleController) -> None:
    vehicle.start()

    snapshot = vehicle.drive(100, Gear.NEUTRAL)

    assert snapshot.state == VehicleState.READY
    assert snapshot.torque_nm == 0


def test_park_with_torque_is_invalid_command(vehicle: VehicleController) -> None:
    vehicle.start()

    snapshot = vehicle.drive(100, Gear.PARK)

    assert snapshot.state == VehicleState.FAULT
    assert snapshot.fault == FaultCode.INVALID_COMMAND


def test_motor_over_temperature_reaches_fault() -> None:
    motor = MotorController(MotorConfig(over_temperature_celsius=36))
    vehicle = VehicleController(motor=motor)
    vehicle.start()

    snapshot = vehicle.drive(200)

    assert snapshot.state == VehicleState.FAULT
    assert snapshot.fault == FaultCode.OVER_TEMPERATURE


def test_stop_reduces_speed(vehicle: VehicleController) -> None:
    vehicle.start()
    driving = vehicle.drive(160)

    stopped = vehicle.stop()

    assert stopped.speed_deci_kph < driving.speed_deci_kph


def test_idle_ticks_cool_vehicle(vehicle: VehicleController) -> None:
    vehicle.start()
    hot = vehicle.drive(250)

    vehicle.stop()
    cooled = vehicle.tick()

    assert cooled.motor_temperature_celsius <= hot.motor_temperature_celsius


def test_repeated_drive_reduces_soc(vehicle: VehicleController) -> None:
    vehicle.start()
    before = vehicle.snapshot().soc_percent

    for _ in range(5):
        vehicle.drive(200)

    assert vehicle.snapshot().soc_percent <= before


def test_vehicle_scenario_completes_under_budget(vehicle: VehicleController) -> None:
    start = perf_counter()

    vehicle.start()
    for _ in range(20):
        vehicle.drive(120)
    vehicle.stop()

    assert perf_counter() - start < 1.0
