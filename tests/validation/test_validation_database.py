"""Level 6 - Database.

Validates the persistence / history claims:
  - test results are saved to SQLite
  - historical runs are retrieved (newest first)
  - failure information is preserved (reason, steps, per-run results)
  - scheduler statistics are updated (failure rates, durations, pass rate)
"""

from __future__ import annotations

import time

import pytest

from vehicle_validation.automation.results import StepResult, TestResult, TestRun
from vehicle_validation.database.history import HistoryStore
from tests.validation.conftest import make_run


def test_results_are_saved_and_counted(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.save_run(make_run("r1", passed=2, failed=1))

    statistics = store.statistics()

    assert statistics["runs"] == 1
    assert statistics["tests"] == 3
    assert statistics["passed"] == 2
    assert statistics["failed"] == 1
    assert statistics["pass_rate"] == pytest.approx(2 / 3)


def test_multiple_runs_are_saved(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.save_run(make_run("r1"))
    store.save_run(make_run("r2"))

    assert store.statistics()["runs"] == 2
    assert {run["run_id"] for run in store.list_runs()} == {"r1", "r2"}


def test_history_retrieved_newest_first(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.save_run(make_run("older"))
    time.sleep(0.02)
    store.save_run(make_run("newer"))

    runs = store.list_runs()

    assert [run["run_id"] for run in runs] == ["newer", "older"]


def test_failure_information_is_preserved(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    test_run = TestRun.create("fail-run", {"strategy": "composite"})
    test_run.add(
        TestResult(
            "drive_command_produces_speed_and_torque",
            False,
            0.42,
            steps=[StepResult("drive", False, 0.42, "expected 100 Nm, got 0")],
            failure_reason="expected 100 Nm, got 0",
        )
    )
    store.save_run(test_run)

    detail = store.run_details("fail-run")

    assert detail is not None
    result = detail["results"][0]
    assert result["passed"] == 0
    assert result["failure_reason"] == "expected 100 Nm, got 0"
    assert result["steps"][0]["passed"] == 0


def test_run_details_include_metadata_and_full_results(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    test_run = TestRun.create("meta-run", {"strategy": "random", "seed": "3"})
    test_run.add(TestResult("startup", True, 0.01))
    test_run.add(TestResult("drive", False, 0.1, failure_reason="defect"))

    store.save_run(test_run)
    detail = store.run_details("meta-run")

    assert detail["run_id"] == "meta-run"
    assert detail["metadata"] == {"strategy": "random", "seed": "3"}
    assert len(detail["results"]) == 2
    assert detail["total"] == 2 and detail["passed"] == 1 and detail["failed"] == 1


def test_missing_run_returns_none(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")

    assert store.run_details("never-saved") is None


def test_scheduler_statistics_updated_by_history(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    failing = TestRun.create("fail", {"strategy": "composite"})
    failing.add(TestResult("drive_command_produces_speed_and_torque", False, 1.2))
    store.save_run(failing)

    drive = store.test_profiles()["drive_command_produces_speed_and_torque"]
    assert drive["runs"] == 1
    assert drive["failure_rate"] == pytest.approx(1.0)
    assert drive["average_duration_seconds"] == pytest.approx(1.2)

    passing = TestRun.create("pass")
    passing.add(TestResult("drive_command_produces_speed_and_torque", True, 0.2))
    store.save_run(passing)

    drive = store.test_profiles()["drive_command_produces_speed_and_torque"]
    assert drive["runs"] == 2
    assert drive["failure_rate"] == pytest.approx(0.5)
    assert drive["average_duration_seconds"] == pytest.approx((1.2 + 0.2) / 2)


def test_save_run_is_idempotent_complete_replace(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.save_run(make_run("same", passed=3, failed=0))
    store.save_run(make_run("same", passed=1, failed=1))

    detail = store.run_details("same")

    assert detail is not None
    assert detail["total"] == 2
    assert detail["passed"] == 1 and detail["failed"] == 1
    assert len(detail["results"]) == 2