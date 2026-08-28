from vehicle_validation.canbus.protocol import FaultCode, Gear, VehicleState, make_motor_status, make_vcu_command
from vehicle_validation.ecu.vcu import VehicleControlUnit, VcuConfig


def test_vcu_latches_communication_timeout_without_fresh_motor_status() -> None:
    vcu = VehicleControlUnit(VcuConfig(motor_status_timeout_ticks=2))
    vcu.receive(make_vcu_command(True, Gear.DRIVE, 50))
    vcu.receive(make_motor_status(VehicleState.DRIVE, 500, 50, 35, FaultCode.NONE))

    vcu.publish()
    vcu.publish()
    status = vcu.publish()

    assert status.data[0] == VehicleState.FAULT
    assert status.data[6] == FaultCode.COMMUNICATION_TIMEOUT
