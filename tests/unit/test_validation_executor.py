import vehicle_validation.automation.executor as executor_module
from tests.unit.test_bus_vehicle_controller import FakeEcuTransport
from vehicle_validation.automation.executor import ValidationExecutor
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.database.history import HistoryStore


class FakeSupervisor:
    def __init__(self, config=None) -> None:
        self.config = config
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class RaisingSupervisor(FakeSupervisor):
    def start(self) -> None:
        self.started = True
        raise RuntimeError("no bus channel")


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


def test_validation_executor_emits_progress_events(tmp_path) -> None:
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")
    events: list[dict] = []

    ValidationExecutor(history, logger).run(strategy_name="composite", seed=2, on_event=events.append)

    names = [event["event"] for event in events]
    assert names[0] == "run.started"
    assert names[-1] == "run.completed"
    assert names.count("test.started") == names.count("test.passed")


def test_validation_executor_runs_on_bus_when_channel_available(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "can_channel_available", lambda channel: True)
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")
    supervisor = FakeSupervisor()
    events: list[dict] = []

    executor = ValidationExecutor(
        history,
        logger,
        channel="vcan0",
        supervisor_factory=lambda config: supervisor,
        transport_factory=lambda config: FakeEcuTransport(),
    )
    test_run = executor.run(strategy_name="composite", seed=1, on_event=events.append)

    assert supervisor.started and supervisor.stopped
    assert test_run.metadata["mode"] == "socketcan-processes"
    assert len(test_run.results) == 3
    assert all(result.passed for result in test_run.results)
    assert {"run.started", "run.completed"}.issubset({event["event"] for event in events})
    assert test_run.results[-1].duration_seconds > 0


def test_validation_executor_delay_fault_stays_in_process(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "can_channel_available", lambda channel: True)
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")

    executor = ValidationExecutor(
        history,
        logger,
        channel="vcan0",
        supervisor_factory=lambda config: FakeSupervisor(),
        transport_factory=lambda config: FakeEcuTransport(),
    )
    test_run = executor.run(strategy_name="composite", seed=1, enable_delay_fault=True)

    assert test_run.metadata["mode"] == "in-process-fallback"


def test_validation_executor_falls_back_when_bus_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "can_channel_available", lambda channel: True)
    history = HistoryStore(tmp_path / "history.sqlite3")
    logger = StructuredLogger(tmp_path / "validation.jsonl")

    executor = ValidationExecutor(
        history,
        logger,
        channel="vcan0",
        supervisor_factory=lambda config: RaisingSupervisor(),
        transport_factory=lambda config: FakeEcuTransport(),
    )
    test_run = executor.run(strategy_name="composite", seed=1)

    assert test_run.metadata["mode"] == "in-process-fallback"
    assert len(test_run.results) == 5
    assert history.statistics()["runs"] == 1