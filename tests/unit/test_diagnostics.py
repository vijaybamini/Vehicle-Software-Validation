from vehicle_validation.automation.diagnostics import build_failure_diagnostic
from vehicle_validation.canbus.protocol import FaultCode, VehicleState, make_motor_status


def test_failure_diagnostic_contains_expected_actual_fault_and_can_trace() -> None:
    frame = make_motor_status(VehicleState.FAULT, 0, 0, 110, FaultCode.OVER_TEMPERATURE)

    diagnostic = build_failure_diagnostic(
        test_name="motor over temperature",
        expected="vehicle remains driveable",
        actual="vehicle entered fault",
        fault=FaultCode.OVER_TEMPERATURE,
        duration_seconds=0.25,
        can_frames=[frame],
    )
    payload = diagnostic.to_dict()

    assert payload["expected"] == "vehicle remains driveable"
    assert payload["actual"] == "vehicle entered fault"
    assert payload["fault"] == "over_temperature"
    assert payload["can_trace"][0]["arbitration_id"] == "0x302"
