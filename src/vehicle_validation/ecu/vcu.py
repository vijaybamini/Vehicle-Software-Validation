"""Vehicle-control-unit ECU simulation."""

from __future__ import annotations

from dataclasses import dataclass

from vehicle_validation.canbus.protocol import (
    CanFrame,
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_motor_command,
    make_vcu_status,
)


@dataclass
class VcuConfig:
    max_torque_nm: int = 250
    default_speed_limit_rpm: int = 7000
    max_regen_percent: int = 30


@dataclass
class VcuState:
    enabled: bool = False
    gear: Gear = Gear.PARK
    torque_request_nm: int = 0
    regen_percent: int = 0
    motor_speed_rpm: int = 0
    motor_torque_nm: int = 0
    fault: FaultCode = FaultCode.NONE


class VehicleControlUnit:
    """VCU model that accepts driver commands and emits motor commands."""

    def __init__(self, config: VcuConfig | None = None) -> None:
        self.config = config or VcuConfig()
        self.state = VcuState()

    def receive(self, frame: CanFrame) -> None:
        if frame.arbitration_id == MessageId.VCU_COMMAND:
            self._receive_driver_command(frame)
        elif frame.arbitration_id == MessageId.BMS_STATUS:
            self._receive_bms_status(frame)
        elif frame.arbitration_id == MessageId.MOTOR_STATUS:
            self._receive_motor_status(frame)

    def motor_command(self) -> CanFrame:
        if self.state.fault != FaultCode.NONE or not self.state.enabled:
            return make_motor_command(False, 0, self.config.default_speed_limit_rpm)

        torque = self.state.torque_request_nm
        if self.state.gear == Gear.REVERSE:
            torque = -abs(torque)
        elif self.state.gear != Gear.DRIVE:
            torque = 0

        torque = max(-self.config.max_torque_nm, min(self.config.max_torque_nm, torque))
        return make_motor_command(True, torque, self.config.default_speed_limit_rpm)

    def publish(self) -> CanFrame:
        speed_deci_kph = round(self.state.motor_speed_rpm * 0.012)
        return make_vcu_status(
            self.vehicle_state,
            self.state.gear,
            speed_deci_kph,
            self.state.motor_torque_nm,
            self.state.fault,
        )

    @property
    def vehicle_state(self) -> VehicleState:
        if self.state.fault != FaultCode.NONE:
            return VehicleState.FAULT
        if self.state.enabled and self.state.gear in {Gear.DRIVE, Gear.REVERSE}:
            return VehicleState.DRIVE
        if self.state.enabled:
            return VehicleState.READY
        return VehicleState.OFF

    def _receive_driver_command(self, frame: CanFrame) -> None:
        self.state.enabled = bool(frame.data[0])
        self.state.gear = Gear(frame.data[1])
        self.state.torque_request_nm = int.from_bytes(frame.data[2:4], "big", signed=True)
        self.state.regen_percent = min(frame.data[4], self.config.max_regen_percent)

        if self.state.enabled and self.state.gear == Gear.PARK and self.state.torque_request_nm != 0:
            self.state.fault = FaultCode.INVALID_COMMAND

    def _receive_bms_status(self, frame: CanFrame) -> None:
        fault = FaultCode(frame.data[7])
        if fault != FaultCode.NONE:
            self.state.fault = fault
            self.state.enabled = False

    def _receive_motor_status(self, frame: CanFrame) -> None:
        self.state.motor_speed_rpm = int.from_bytes(frame.data[1:3], "big", signed=False)
        self.state.motor_torque_nm = int.from_bytes(frame.data[3:5], "big", signed=True)
        fault = FaultCode(frame.data[6])
        if fault != FaultCode.NONE:
            self.state.fault = fault
            self.state.enabled = False
