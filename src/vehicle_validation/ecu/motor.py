"""Motor-controller ECU simulation."""

from __future__ import annotations

from dataclasses import dataclass

from vehicle_validation.canbus.protocol import (
    CanFrame,
    FaultCode,
    MessageId,
    VehicleState,
    make_motor_status,
)


@dataclass
class MotorConfig:
    max_torque_nm: int = 300
    max_speed_rpm: int = 9000
    over_temperature_celsius: int = 105
    cooling_per_tick_celsius: int = 1


@dataclass
class MotorState:
    enabled: bool = False
    speed_rpm: int = 0
    torque_nm: int = 0
    temperature_celsius: int = 35
    fault: FaultCode = FaultCode.NONE


class MotorController:
    """Deterministic motor model driven by `MOTOR_COMMAND` frames."""

    def __init__(self, config: MotorConfig | None = None) -> None:
        self.config = config or MotorConfig()
        self.state = MotorState()

    def receive(self, frame: CanFrame) -> None:
        if frame.arbitration_id != MessageId.MOTOR_COMMAND:
            return

        enabled = bool(frame.data[0])
        torque_request = int.from_bytes(frame.data[1:3], "big", signed=True)
        speed_limit = int.from_bytes(frame.data[3:5], "big", signed=False)
        self.command(enabled, torque_request, speed_limit)

    def command(self, enabled: bool, torque_request_nm: int, speed_limit_rpm: int) -> None:
        if self.state.fault != FaultCode.NONE:
            self.state.enabled = False
            self.state.torque_nm = 0
            return

        self.state.enabled = enabled
        if not enabled:
            self.state.torque_nm = 0
            self.state.speed_rpm = max(0, self.state.speed_rpm - 250)
            return

        torque = max(-self.config.max_torque_nm, min(self.config.max_torque_nm, torque_request_nm))
        self.state.torque_nm = torque
        target_speed = min(self.config.max_speed_rpm, max(0, speed_limit_rpm))
        self.state.speed_rpm = min(target_speed, self.state.speed_rpm + abs(torque) * 8)
        self.state.temperature_celsius += max(abs(torque) // 100, 1)
        self._update_faults()

    def tick(self) -> None:
        self._update_faults()
        if self.state.fault != FaultCode.NONE:
            return
        if not self.state.enabled:
            self.state.speed_rpm = max(0, self.state.speed_rpm - 100)
            self.state.temperature_celsius = max(
                25,
                self.state.temperature_celsius - self.config.cooling_per_tick_celsius,
            )
        self._update_faults()

    def publish(self) -> CanFrame:
        return make_motor_status(
            self.vehicle_state,
            self.state.speed_rpm,
            self.state.torque_nm,
            self.state.temperature_celsius,
            self.state.fault,
        )

    @property
    def vehicle_state(self) -> VehicleState:
        if self.state.fault != FaultCode.NONE:
            return VehicleState.FAULT
        if self.state.enabled:
            return VehicleState.DRIVE
        return VehicleState.READY

    def _update_faults(self) -> None:
        if self.state.temperature_celsius >= self.config.over_temperature_celsius:
            self.state.fault = FaultCode.OVER_TEMPERATURE
            self.state.enabled = False
            self.state.torque_nm = 0
        elif self.state.fault == FaultCode.NONE:
            self.state.fault = FaultCode.NONE
