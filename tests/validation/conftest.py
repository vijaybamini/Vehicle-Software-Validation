"""Shared fixtures and helpers for the validation campaign suite.

Each validation module corresponds to one level of the resume test plan:

   1  ECU communication
   2  pytest automation framework
   3  Functional testing
   4  Fault injection
   5  Performance testing
   6  Database
   7  Scheduler
   8  Experiment
   9  Dashboard
   10 Integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vehicle_validation.automation.executor import ValidationExecutor
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.automation.results import TestResult, TestRun
from vehicle_validation.backend import app
from vehicle_validation.database.history import HistoryStore
from tests.unit.test_bus_vehicle_controller import FakeEcuTransport


class FakeSupervisor:
    """Hermetic stand-in for ``EcuSupervisor`` used by bus-mode validation."""

    def __init__(self, config=None) -> None:
        self.config = config
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def build_components(root: Path) -> tuple[HistoryStore, StructuredLogger, ValidationExecutor]:
    history = HistoryStore(root / "history.sqlite3")
    logger = StructuredLogger(root / "validation.jsonl")
    executor = ValidationExecutor(history, logger, channel="vcan0")
    return history, logger, executor


@pytest.fixture
def components(tmp_path) -> tuple[HistoryStore, StructuredLogger, ValidationExecutor]:
    return build_components(tmp_path)


@pytest.fixture
def backend(monkeypatch, components):
    """FastAPI app wired to an isolated history store + executor."""
    history, logger, executor = components
    monkeypatch.setattr(app, "history", history)
    monkeypatch.setattr(app, "structured_logger", logger)
    monkeypatch.setattr(app, "executor", executor)
    return app


def make_run(run_id: str = "run-x", passed: int = 1, failed: int = 0) -> TestRun:
    test_run = TestRun.create(run_id)
    for index in range(passed):
        test_run.add(TestResult(f"pass_{index}", True, 0.05 + index / 1000))
    for index in range(failed):
        test_run.add(
            TestResult(
                f"fail_{index}",
                False,
                0.1 + index / 1000,
                failure_reason=f"validation defect {index}",
            )
        )
    return test_run


__all__ = ["FakeEcuTransport", "FakeSupervisor", "build_components", "make_run"]