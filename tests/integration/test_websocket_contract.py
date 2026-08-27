from vehicle_validation.backend.app import vehicle_status


def test_websocket_status_uses_vehicle_status_contract() -> None:
    payload = vehicle_status()

    assert {"state", "gear", "speed_deci_kph", "fault"}.issubset(payload)
