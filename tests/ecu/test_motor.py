from vehicle_validation.canbus.protocol import (
    FaultCode,
    MessageId,
    VehicleState,
    make_motor_command,
)
from vehicle_validation.ecu.motor import MotorConfig, MotorController


def test_motor_accepts_command_frame() -> None:
    motor = MotorController()

    motor.receive(make_motor_command(True, 120, 3000))
    status = motor.publish()

    assert status.arbitration_id == MessageId.MOTOR_STATUS
    assert status.data[0] == VehicleState.DRIVE
    assert int.from_bytes(status.data[3:5], "big", signed=True) == 120


def test_motor_clamps_torque_request() -> None:
    motor = MotorController(MotorConfig(max_torque_nm=200))

    motor.receive(make_motor_command(True, 999, 3000))

    assert motor.state.torque_nm == 200


def test_motor_reports_over_temperature_fault() -> None:
    motor = MotorController(MotorConfig(over_temperature_celsius=40))
    motor.state.temperature_celsius = 40

    motor.tick()
    status = motor.publish()

    assert status.data[0] == VehicleState.FAULT
    assert status.data[6] == FaultCode.OVER_TEMPERATURE
