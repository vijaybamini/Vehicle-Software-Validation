"""Vehicle-level control API over the simulated ECUs."""

from __future__ import annotations

from dataclasses import dataclass

from vehicle_validation.canbus.protocol import FaultCode, Gear, VehicleState, make_vcu_command
from vehicle_validation.ecu.bms import BatteryManagementSystem
from vehicle_validation.ecu.motor import MotorController
from vehicle_validation.ecu.vcu import VehicleControlUnit


@dataclass(frozen=True)
class VehicleSnapshot:
    state: VehicleState
    gear: Gear
    speed_deci_kph: int
    torque_nm: int
    soc_percent: int
    battery_temperature_celsius: int
    motor_temperature_celsius: int
    fault: FaultCode


class VehicleController:
    """High-level API used by tests and backend routes."""

    def __init__(
        self,
        bms: BatteryManagementSystem | None = None,
        vcu: VehicleControlUnit | None = None,
        motor: MotorController | None = None,
    ) -> None:
        self.bms = bms or BatteryManagementSystem()
        self.vcu = vcu or VehicleControlUnit()
        self.motor = motor or MotorController()

    def start(self) -> VehicleSnapshot:
        self.vcu.receive(make_vcu_command(True, Gear.NEUTRAL, 0))
        self._exchange_frames()
        return self.snapshot()

    def drive(self, torque_nm: int, gear: Gear = Gear.DRIVE, regen_percent: int = 0) -> VehicleSnapshot:
        self.vcu.receive(make_vcu_command(True, gear, torque_nm, regen_percent))
        self.bms.apply_load(torque_nm, regen_percent)
        self._exchange_frames()
        return self.snapshot()

    def stop(self) -> VehicleSnapshot:
        self.vcu.receive(make_vcu_command(False, Gear.PARK, 0))
        self.motor.command(False, 0, 0)
        self.bms.cool()
        self._exchange_frames()
        return self.snapshot()

    def tick(self) -> VehicleSnapshot:
        self.motor.tick()
        self.bms.cool()
        self._exchange_frames()
        return self.snapshot()

    def snapshot(self) -> VehicleSnapshot:
        vcu_status = self.vcu.publish()
        return VehicleSnapshot(
            state=VehicleState(vcu_status.data[0]),
            gear=Gear(vcu_status.data[1]),
            speed_deci_kph=int.from_bytes(vcu_status.data[2:4], "big", signed=False),
            torque_nm=int.from_bytes(vcu_status.data[4:6], "big", signed=True),
            soc_percent=round(self.bms.state.soc_percent),
            battery_temperature_celsius=self.bms.state.max_temperature_celsius,
            motor_temperature_celsius=self.motor.state.temperature_celsius,
            fault=FaultCode(vcu_status.data[6]),
        )

    def _exchange_frames(self) -> None:
        for frame in self.bms.publish():
            self.vcu.receive(frame)
        self.motor.receive(self.vcu.motor_command())
        self.vcu.receive(self.motor.publish())
