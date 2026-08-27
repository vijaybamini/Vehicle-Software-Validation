from vehicle_validation.automation.executor import ValidationExecutor
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.database.history import HistoryStore


def test_validation_executor_runs_and_saves_history(tmp_path) -> None:
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")

    test_run = ValidationExecutor(history, logger).run(strategy_name="composite", seed=2)

    assert test_run.results
    assert history.statistics()["runs"] == 1


def test_validation_executor_uses_recorded_history_for_test_cases(tmp_path) -> None:
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")
    executor = ValidationExecutor(history, logger)

    executor.run(strategy_name="composite", seed=2, enable_delay_fault=True)
    tests = {test.name: test for test in executor.tests_with_history()}

    assert any(test.historical_failure_rate > 0 for test in tests.values())
