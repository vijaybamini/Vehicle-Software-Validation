from vehicle_validation.backend.app import diagnostics


def test_diagnostics_endpoint_returns_records() -> None:
    records = diagnostics()

    assert records
    assert "event" in records[0]
    assert "payload" in records[0]
