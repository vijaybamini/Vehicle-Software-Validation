from vehicle_validation.canbus.protocol import FaultCode, Gear, VehicleState
from vehicle_validation.ecu.bms import BatteryManagementSystem, BmsConfig
from vehicle_validation.vehicle.controller import VehicleController


def test_startup_reaches_ready_state(vehicle: VehicleController) -> None:
    snapshot = vehicle.start()

    assert snapshot.state == VehicleState.READY
    assert snapshot.fault == FaultCode.NONE


def test_drive_command_produces_speed_and_torque(vehicle: VehicleController) -> None:
    vehicle.start()

    snapshot = vehicle.drive(100, Gear.DRIVE)

    assert snapshot.state == VehicleState.DRIVE
    assert snapshot.speed_deci_kph > 0
    assert snapshot.torque_nm == 100


def test_reverse_command_produces_negative_torque(vehicle: VehicleController) -> None:
    vehicle.start()

    snapshot = vehicle.drive(80, Gear.REVERSE)

    assert snapshot.state == VehicleState.DRIVE
    assert snapshot.torque_nm == -80


def test_regen_preserves_or_increases_soc() -> None:
    vehicle = VehicleController()
    vehicle.start()
    before = vehicle.snapshot().soc_percent

    after = vehicle.drive(-20, Gear.DRIVE, regen_percent=20)

    assert after.soc_percent >= before


def test_low_soc_forces_vehicle_fault() -> None:
    bms = BatteryManagementSystem(BmsConfig(low_soc_threshold=79.0))
    vehicle = VehicleController(bms=bms)
    vehicle.start()

    snapshot = vehicle.drive(3000, Gear.DRIVE)

    assert snapshot.state == VehicleState.FAULT
    assert snapshot.fault == FaultCode.LOW_SOC
