from vehicle_validation.canbus.protocol import Gear, VehicleState
from vehicle_validation.vehicle.controller import VehicleController


def test_vehicle_starts_in_ready_state() -> None:
    vehicle = VehicleController()

    snapshot = vehicle.start()

    assert snapshot.state == VehicleState.READY
    assert snapshot.gear == Gear.NEUTRAL


def test_vehicle_drives_with_positive_torque() -> None:
    vehicle = VehicleController()
    vehicle.start()

    snapshot = vehicle.drive(120)

    assert snapshot.state == VehicleState.DRIVE
    assert snapshot.torque_nm == 120
    assert snapshot.speed_deci_kph > 0


def test_vehicle_stop_returns_to_off() -> None:
    vehicle = VehicleController()
    vehicle.start()
    vehicle.drive(120)

    snapshot = vehicle.stop()

    assert snapshot.state == VehicleState.OFF
    assert snapshot.gear == Gear.PARK
