"""Level 5 - Performance testing.

Validates the performance claims available without physical hardware:
  - CAN response latency on the bus driver path (driver command -> snapshot)
  - suite execution time budgets
  - timeout behavior (quiet bus settles, empty receive returns quickly)
  - frame throughput through the transport and fault injector

NOTE: real vcan cadence (0.1s motor/VCU, 0.2s BMS loops) cannot be measured
here because `vcan0` requires root; the loop intervals are asserted as
configuration in Level 1.
"""

from __future__ import annotations

from time import perf_counter

import pytest

from vehicle_validation.automation.faults import MessageDelayInjector
from vehicle_validation.canbus.protocol import FaultCode, Gear, MessageId, VehicleState, make_bms_status
from vehicle_validation.vehicle.bus_controller import BusVehicleController
from tests.unit.test_bus_vehicle_controller import FakeEcuTransport

LATENCY_BUDGET_SECONDS = 1.0
RUN_BUDGET_SECONDS = 5.0
SETTLE_BOUND_SECONDS = 3.0
THROUGHPUT_FRAMES = 1000
THROUGHPUT_BUDGET_SECONDS = 2.0

_BMS_FRAME = make_bms_status(VehicleState.READY, 80, 99, 3600, 0, FaultCode.NONE)


def test_can_response_latency_bus_drive_within_budget() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())
    vehicle.start()

    start = perf_counter()
    snapshot = vehicle.drive(100, Gear.DRIVE)
    latency = perf_counter() - start

    assert snapshot.torque_nm == 100
    assert latency < LATENCY_BUDGET_SECONDS
    assert vehicle.can_trace  # CAN frames actually flowed


def test_bus_settle_is_bounded_on_quiet_bus() -> None:
    class QuietTransport(FakeEcuTransport):
        def __init__(self) -> None:
            super().__init__()
            self._frames.clear()

        def send(self, frame) -> None:  # type: ignore[override]
            pass

        def receive(self, timeout: float = 0.1):
            return None

    vehicle = BusVehicleController(QuietTransport())

    start = perf_counter()
    snapshot = vehicle.drive(100, Gear.DRIVE)
    elapsed = perf_counter() - start

    assert snapshot is not None
    assert elapsed < SETTLE_BOUND_SECONDS


def test_full_suite_execution_within_budget(components) -> None:
    history, logger, executor = components

    start = perf_counter()
    test_run = executor.run(strategy_name="composite", seed=1)
    elapsed = perf_counter() - start

    assert test_run.passed == len(test_run.results)
    assert elapsed < RUN_BUDGET_SECONDS


def test_recorded_execution_durations_are_sane(components) -> None:
    history, logger, executor = components

    test_run = executor.run(strategy_name="composite", seed=1)

    assert all(0 < result.duration_seconds < RUN_BUDGET_SECONDS for result in test_run.results)
    assert sum(result.duration_seconds for result in test_run.results) > 0


def test_receive_timeout_returns_none_promptly() -> None:
    transport = FakeEcuTransport()
    transport._frames.clear()

    start = perf_counter()
    frame = transport.receive(timeout=0.01)
    elapsed = perf_counter() - start

    assert frame is None
    assert elapsed < 0.1


def test_frame_throughput_through_transport() -> None:
    transport = FakeEcuTransport()

    start = perf_counter()
    for _ in range(THROUGHPUT_FRAMES):
        transport.send(_BMS_FRAME)
    elapsed = perf_counter() - start

    assert len(transport.sent) == THROUGHPUT_FRAMES
    assert elapsed < THROUGHPUT_BUDGET_SECONDS


def test_injector_throughput_with_non_target_frames() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=3)

    start = perf_counter()
    for _ in range(THROUGHPUT_FRAMES):
        injector.inject(_BMS_FRAME)
    elapsed = perf_counter() - start

    assert injector.pending_count == 0
    assert elapsed < THROUGHPUT_BUDGET_SECONDS