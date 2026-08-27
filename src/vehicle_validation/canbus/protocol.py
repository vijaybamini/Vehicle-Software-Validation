"""CAN message identifiers and fixed-width payload encoding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class MessageId(IntEnum):
    BMS_STATUS = 0x101
    BMS_TEMPERATURE = 0x102
    VCU_COMMAND = 0x201
    VCU_STATUS = 0x202
    MOTOR_COMMAND = 0x301
    MOTOR_STATUS = 0x302


class VehicleState(IntEnum):
    OFF = 0
    READY = 1
    DRIVE = 2
    FAULT = 3


class ThermalState(IntEnum):
    NORMAL = 0
    WARM = 1
    HOT = 2
    CRITICAL = 3


class Gear(IntEnum):
    PARK = 0
    REVERSE = 1
    NEUTRAL = 2
    DRIVE = 3


class FaultCode(IntEnum):
    NONE = 0
    LOW_SOC = 1
    OVER_TEMPERATURE = 2
    OVER_CURRENT = 3
    COMMUNICATION_TIMEOUT = 4
    INVALID_COMMAND = 5


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.arbitration_id <= 0x7FF:
            raise ValueError("arbitration_id must fit a standard 11-bit CAN ID")
        if len(self.data) != 8:
            raise ValueError("CAN payloads must be exactly 8 bytes")


def _u8(value: int) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{value} is outside uint8 range")
    return value


def _u16(value: int) -> bytes:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"{value} is outside uint16 range")
    return value.to_bytes(2, "big", signed=False)


def _i16(value: int) -> bytes:
    if not -0x8000 <= value <= 0x7FFF:
        raise ValueError(f"{value} is outside int16 range")
    return value.to_bytes(2, "big", signed=True)


def make_bms_status(
    state: VehicleState,
    soc_percent: int,
    soh_percent: int,
    pack_voltage_decivolts: int,
    current_deciamps: int,
    fault: FaultCode = FaultCode.NONE,
) -> CanFrame:
    data = bytes(
        [
            state,
            _u8(soc_percent),
            _u8(soh_percent),
        ]
    )
    data += _u16(pack_voltage_decivolts)
    data += _i16(current_deciamps)
    data += bytes([fault])
    return CanFrame(MessageId.BMS_STATUS, data)


def make_bms_temperature(
    min_celsius: int,
    max_celsius: int,
    average_celsius: int,
    thermal_state: ThermalState,
) -> CanFrame:
    data = bytes(
        [
            _u8(min_celsius),
            _u8(max_celsius),
            _u8(average_celsius),
            thermal_state,
            0,
            0,
            0,
            0,
        ]
    )
    return CanFrame(MessageId.BMS_TEMPERATURE, data)


def make_vcu_command(
    enable: bool,
    gear: Gear,
    torque_request_nm: int,
    regen_percent: int = 0,
) -> CanFrame:
    data = bytes([int(enable), gear])
    data += _i16(torque_request_nm)
    data += bytes([_u8(regen_percent), 0, 0, 0])
    return CanFrame(MessageId.VCU_COMMAND, data)


def make_vcu_status(
    state: VehicleState,
    gear: Gear,
    speed_deci_kph: int,
    torque_nm: int,
    fault: FaultCode = FaultCode.NONE,
) -> CanFrame:
    data = bytes([state, gear])
    data += _u16(speed_deci_kph)
    data += _i16(torque_nm)
    data += bytes([fault, 0])
    return CanFrame(MessageId.VCU_STATUS, data)


def make_motor_command(
    enable: bool,
    torque_request_nm: int,
    speed_limit_rpm: int,
) -> CanFrame:
    data = bytes([int(enable)])
    data += _i16(torque_request_nm)
    data += _u16(speed_limit_rpm)
    data += bytes([0, 0, 0])
    return CanFrame(MessageId.MOTOR_COMMAND, data)


def make_motor_status(
    state: VehicleState,
    speed_rpm: int,
    torque_nm: int,
    temperature_celsius: int,
    fault: FaultCode = FaultCode.NONE,
) -> CanFrame:
    data = bytes([state])
    data += _u16(speed_rpm)
    data += _i16(torque_nm)
    data += bytes([_u8(temperature_celsius), fault, 0])
    return CanFrame(MessageId.MOTOR_STATUS, data)
