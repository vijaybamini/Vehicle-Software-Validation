from vehicle_validation.canbus.protocol import FaultCode, MessageId, ThermalState, VehicleState
from vehicle_validation.ecu.bms import BatteryManagementSystem, BmsConfig


def test_bms_publishes_status_and_temperature_frames() -> None:
    bms = BatteryManagementSystem()

    frames = bms.publish()

    assert [frame.arbitration_id for frame in frames] == [
        MessageId.BMS_STATUS,
        MessageId.BMS_TEMPERATURE,
    ]
    assert all(len(frame.data) == 8 for frame in frames)


def test_bms_reports_low_soc_fault() -> None:
    bms = BatteryManagementSystem(BmsConfig(low_soc_threshold=79.0))

    bms.apply_load(torque_nm=3000)

    status = bms.publish()[0]
    assert status.data[0] == VehicleState.FAULT
    assert status.data[7] == FaultCode.LOW_SOC


def test_bms_reports_thermal_state() -> None:
    bms = BatteryManagementSystem()
    bms.state.max_temperature_celsius = 56

    temperature = bms.publish()[1]

    assert temperature.data[3] == ThermalState.HOT
