"""Vehicle control API driven over a live CAN transport.

This controller lets the validation framework treat the running BMS / VCU /
motor ECU processes as the vehicle under test.  Each high-level operation
sends a `VCU_COMMAND` frame and settles on the published status frames, so the
scenario steps never need to know whether the vehicle is simulated in-process
or running on a real (virtual) CAN bus.
"""

from __future__ import annotations

from vehicle_validation.canbus.protocol import (
    CanFrame,
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_vcu_command,
)
from vehicle_validation.canbus.transport import CanTransport
from vehicle_validation.vehicle.controller import VehicleSnapshot

_STATUS_IDS = {
    MessageId.BMS_STATUS,
    MessageId.BMS_TEMPERATURE,
    MessageId.VCU_STATUS,
    MessageId.MOTOR_STATUS,
}


class BusVehicleController:
    """High-level vehicle API that exchanges frames with running ECU processes."""

    def __init__(
        self,
        transport: CanTransport,
        settle_attempts: int = 40,
        idle_timeout: float = 0.05,
    ) -> None:
        self._transport = transport
        self._settle_attempts = settle_attempts
        self._idle_timeout = idle_timeout
        self._latest: dict[int, CanFrame] = {}
        self.can_trace: list[CanFrame] = []

    def start(self) -> VehicleSnapshot:
        self._command(make_vcu_command(True, Gear.NEUTRAL, 0))
        return self.snapshot()

    def drive(self, torque_nm: int, gear: Gear = Gear.DRIVE, regen_percent: int = 0) -> VehicleSnapshot:
        self._command(make_vcu_command(True, gear, torque_nm, regen_percent))
        return self.snapshot()

    def stop(self) -> VehicleSnapshot:
        self._command(make_vcu_command(False, Gear.PARK, 0))
        return self.snapshot()

    def tick(self) -> VehicleSnapshot:
        self._latest = self._settle()
        return self.snapshot()

    def snapshot(self) -> VehicleSnapshot:
        status = self._latest.get(int(MessageId.VCU_STATUS))
        state = VehicleState(status.data[0]) if status else VehicleState.OFF
        gear = Gear(status.data[1]) if status else Gear.PARK
        speed_deci_kph = int.from_bytes(status.data[2:4], "big", signed=False) if status else 0
        torque_nm = int.from_bytes(status.data[4:6], "big", signed=True) if status else 0
        fault = FaultCode(status.data[6]) if status else FaultCode.NONE

        bms_status = self._latest.get(int(MessageId.BMS_STATUS))
        soc_percent = bms_status.data[1] if bms_status else 80
        bms_temperature = self._latest.get(int(MessageId.BMS_TEMPERATURE))
        battery_temperature_celsius = bms_temperature.data[1] if bms_temperature else 28
        motor_status = self._latest.get(int(MessageId.MOTOR_STATUS))
        motor_temperature_celsius = motor_status.data[4] if motor_status else 35

        return VehicleSnapshot(
            state=state,
            gear=gear,
            speed_deci_kph=speed_deci_kph,
            torque_nm=torque_nm,
            soc_percent=soc_percent,
            battery_temperature_celsius=battery_temperature_celsius,
            motor_temperature_celsius=motor_temperature_celsius,
            fault=fault,
        )

    def _command(self, frame: CanFrame) -> None:
        self.can_trace.append(frame)
        self._transport.send(frame)
        self._latest = self._settle()

    def _settle(self) -> dict[int, CanFrame]:
        latest: dict[int, CanFrame] = {}
        saw_status = False
        for _ in range(self._settle_attempts):
            frame = self._transport.receive(timeout=self._idle_timeout)
            if frame is None:
                if saw_status:
                    break
                continue
            self.can_trace.append(frame)
            if frame.arbitration_id in _STATUS_IDS:
                latest[int(frame.arbitration_id)] = frame
            if frame.arbitration_id == MessageId.VCU_STATUS:
                saw_status = True
        return latest