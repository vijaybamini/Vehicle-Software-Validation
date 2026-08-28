from vehicle_validation.automation.results import TestResult, TestRun
from vehicle_validation.database.history import HistoryStore


def test_history_store_saves_run(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    test_run = TestRun.create("run-1")
    test_run.add(TestResult("startup", True, 0.01))

    store.save_run(test_run)

    runs = store.list_runs()
    assert runs[0]["run_id"] == "run-1"
    assert runs[0]["passed"] == 1


def test_history_store_reports_statistics(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    test_run = TestRun.create("run-1")
    test_run.add(TestResult("startup", True, 0.01))
    test_run.add(TestResult("drive", False, 0.02, failure_reason="no torque"))

    store.save_run(test_run)

    assert store.statistics()["pass_rate"] == 0.5


def test_history_store_reports_test_profiles(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    first = TestRun.create("run-1")
    first.add(TestResult("drive", True, 0.10))
    second = TestRun.create("run-2")
    second.add(TestResult("drive", False, 0.30, failure_reason="no torque"))

    store.save_run(first)
    store.save_run(second)

    profile = store.test_profiles()["drive"]
    assert profile["runs"] == 2
    assert profile["failure_rate"] == 0.5


def test_history_store_returns_run_details(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    test_run = TestRun.create("run-detail")
    test_run.add(TestResult("startup", True, 0.01))
    test_run.add(TestResult("drive", False, 0.02, failure_reason="no torque"))

    store.save_run(test_run)

    details = store.run_details("run-detail")
    assert details is not None
    assert details["run_id"] == "run-detail"
    assert len(details["results"]) == 2
    assert store.run_details("missing-run") is None
