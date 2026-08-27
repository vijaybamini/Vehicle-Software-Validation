from vehicle_validation.canbus.protocol import (
    FaultCode,
    Gear,
    MessageId,
    ThermalState,
    VehicleState,
    make_bms_status,
    make_bms_temperature,
    make_motor_command,
    make_motor_status,
    make_vcu_command,
    make_vcu_status,
)


def test_message_ids_are_stable() -> None:
    assert MessageId.BMS_STATUS == 0x101
    assert MessageId.BMS_TEMPERATURE == 0x102
    assert MessageId.VCU_COMMAND == 0x201
    assert MessageId.VCU_STATUS == 0x202
    assert MessageId.MOTOR_COMMAND == 0x301
    assert MessageId.MOTOR_STATUS == 0x302


def test_protocol_builders_create_8_byte_frames() -> None:
    frames = [
        make_bms_status(VehicleState.READY, 80, 99, 3600, -120, FaultCode.NONE),
        make_bms_temperature(24, 32, 28, ThermalState.NORMAL),
        make_vcu_command(True, Gear.DRIVE, 120, 5),
        make_vcu_status(VehicleState.DRIVE, Gear.DRIVE, 452, 118, FaultCode.NONE),
        make_motor_command(True, 120, 6000),
        make_motor_status(VehicleState.DRIVE, 1500, 118, 45, FaultCode.NONE),
    ]

    assert all(len(frame.data) == 8 for frame in frames)


def test_signed_values_are_big_endian() -> None:
    frame = make_vcu_command(True, Gear.DRIVE, -25)

    assert frame.data[2:4] == b"\xff\xe7"
