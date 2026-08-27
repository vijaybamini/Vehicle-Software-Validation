# Testing

The test suite is organized by validation level:

- `tests/unit`: protocol, scheduling, storage, and pure helper logic.
- `tests/ecu`: isolated ECU model behavior.
- `tests/functional`: vehicle-level scenarios.
- `tests/integration`: backend, database, and runner integration checks.

Run all tests:

```bash
pytest
```

Run one group:

```bash
pytest tests/ecu
```

The shared fixtures in `tests/conftest.py` create fresh BMS, VCU, motor, and
vehicle-controller instances for each test.
