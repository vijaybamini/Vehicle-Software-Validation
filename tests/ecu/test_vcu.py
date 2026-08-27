from vehicle_validation.canbus.protocol import (
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_bms_status,
    make_motor_status,
    make_vcu_command,
)
from vehicle_validation.ecu.vcu import VehicleControlUnit, VcuConfig


def test_vcu_turns_driver_command_into_motor_command() -> None:
    vcu = VehicleControlUnit()

    vcu.receive(make_vcu_command(True, Gear.DRIVE, 120))
    command = vcu.motor_command()

    assert command.arbitration_id == MessageId.MOTOR_COMMAND
    assert command.data[0] == 1
    assert int.from_bytes(command.data[1:3], "big", signed=True) == 120


def test_vcu_clamps_torque() -> None:
    vcu = VehicleControlUnit(VcuConfig(max_torque_nm=100))

    vcu.receive(make_vcu_command(True, Gear.DRIVE, 300))

    assert int.from_bytes(vcu.motor_command().data[1:3], "big", signed=True) == 100


def test_vcu_latches_bms_fault() -> None:
    vcu = VehicleControlUnit()

    vcu.receive(make_bms_status(VehicleState.FAULT, 10, 99, 3600, 0, FaultCode.LOW_SOC))

    status = vcu.publish()
    assert status.data[0] == VehicleState.FAULT
    assert status.data[6] == FaultCode.LOW_SOC


def test_vcu_reads_motor_status() -> None:
    vcu = VehicleControlUnit()

    vcu.receive(make_motor_status(VehicleState.DRIVE, 1500, 80, 42))

    assert vcu.state.motor_speed_rpm == 1500
    assert vcu.state.motor_torque_nm == 80
