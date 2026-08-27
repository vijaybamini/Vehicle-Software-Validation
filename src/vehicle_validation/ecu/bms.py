"""Battery-management-system ECU simulation."""

from __future__ import annotations

from dataclasses import dataclass

from vehicle_validation.canbus.protocol import (
    CanFrame,
    FaultCode,
    ThermalState,
    VehicleState,
    make_bms_status,
    make_bms_temperature,
)


@dataclass
class BmsConfig:
    nominal_voltage_decivolts: int = 3600
    discharge_per_100_nm: float = 0.05
    charge_per_regen_percent: float = 0.02
    low_soc_threshold: float = 15.0
    hot_temperature_celsius: int = 55
    critical_temperature_celsius: int = 65


@dataclass
class BmsState:
    soc_percent: float = 80.0
    soh_percent: int = 99
    min_temperature_celsius: int = 24
    max_temperature_celsius: int = 28
    average_temperature_celsius: int = 26
    current_deciamps: int = 0
    vehicle_state: VehicleState = VehicleState.READY
    fault: FaultCode = FaultCode.NONE


class BatteryManagementSystem:
    """Small deterministic BMS model for validation tests."""

    def __init__(self, config: BmsConfig | None = None) -> None:
        self.config = config or BmsConfig()
        self.state = BmsState()

    def apply_load(self, torque_nm: int, regen_percent: int = 0) -> None:
        discharge = max(torque_nm, 0) / 100.0 * self.config.discharge_per_100_nm
        charge = max(regen_percent, 0) * self.config.charge_per_regen_percent
        self.state.soc_percent = min(100.0, max(0.0, self.state.soc_percent - discharge + charge))
        self.state.current_deciamps = int(torque_nm * 1.5) - int(regen_percent * 2.0)

        heat = max(abs(torque_nm) // 150, 0)
        self.state.max_temperature_celsius = min(90, self.state.max_temperature_celsius + heat)
        self.state.average_temperature_celsius = round(
            (self.state.min_temperature_celsius + self.state.max_temperature_celsius) / 2
        )
        self._update_faults()

    def cool(self, degrees_celsius: int = 1) -> None:
        self.state.max_temperature_celsius = max(
            self.state.min_temperature_celsius,
            self.state.max_temperature_celsius - max(degrees_celsius, 0),
        )
        self.state.average_temperature_celsius = round(
            (self.state.min_temperature_celsius + self.state.max_temperature_celsius) / 2
        )
        self._update_faults()

    def publish(self) -> list[CanFrame]:
        soc = round(self.state.soc_percent)
        status = make_bms_status(
            self.state.vehicle_state,
            soc,
            self.state.soh_percent,
            self.config.nominal_voltage_decivolts,
            self.state.current_deciamps,
            self.state.fault,
        )
        temperature = make_bms_temperature(
            self.state.min_temperature_celsius,
            self.state.max_temperature_celsius,
            self.state.average_temperature_celsius,
            self.thermal_state,
        )
        return [status, temperature]

    @property
    def thermal_state(self) -> ThermalState:
        if self.state.max_temperature_celsius >= self.config.critical_temperature_celsius:
            return ThermalState.CRITICAL
        if self.state.max_temperature_celsius >= self.config.hot_temperature_celsius:
            return ThermalState.HOT
        if self.state.max_temperature_celsius >= 45:
            return ThermalState.WARM
        return ThermalState.NORMAL

    def _update_faults(self) -> None:
        if self.state.soc_percent < self.config.low_soc_threshold:
            self.state.fault = FaultCode.LOW_SOC
            self.state.vehicle_state = VehicleState.FAULT
            return
        if self.thermal_state in {ThermalState.HOT, ThermalState.CRITICAL}:
            self.state.fault = FaultCode.OVER_TEMPERATURE
            self.state.vehicle_state = VehicleState.FAULT
            return
        self.state.fault = FaultCode.NONE
        self.state.vehicle_state = VehicleState.READY
