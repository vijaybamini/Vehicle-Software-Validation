"""Level 10 - Integration.

Validates the end-to-end platform claims:
  - full pipeline over the live API: catalog -> run -> history -> statistics
  - historical results drive subsequent scheduling across the full stack
  - failure diagnostics recorded for failed runs
  - bus-mode execution path runs end-to-end against a fake transport
  - socketcan-unavailable environments fall back to in-process execution
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

from vehicle_validation.automation.catalog import scenario_catalog
from vehicle_validation.automation.executor import SOCKETCAN_MODE
from tests.validation.conftest import FakeEcuTransport, FakeSupervisor, build_components


def _run_ids(client: TestClient, count: int) -> list[str]:
    listing = client.get("/runs").json()
    assert len(listing) >= count
    return [entry["run_id"] for entry in listing]


def test_end_to_end_clean_pipeline(backend, monkeypatch) -> None:
    with TestClient(backend.app) as client:
        tests = client.get("/tests").json()
        assert len(tests) == 5

        response = client.post(
            "/runs", json={"strategy": "composite", "seed": 1, "enable_delay_fault": False}
        )
        assert response.status_code == 200
        payload = response.json()
        run_id = payload["run_id"]
        assert payload["summary"]["total"] == 5
        assert payload["summary"]["passed"] == 5
        assert payload["metadata"]["mode"] == "in-process-fallback"

        detail = client.get(f"/runs/{run_id}").json()
        assert detail["metadata"]["strategy"] == "composite"
        assert all("steps" in result for result in detail["results"])

        statistics = client.get("/statistics").json()
        assert statistics["runs"] == 1
        assert statistics["passed"] == 5

        comparison = client.get("/scheduler/comparison").json()
        assert len(comparison) == 4


def test_history_drives_subsequent_scheduling(backend) -> None:
    with TestClient(backend.app) as client:
        client.post(
            "/runs", json={"strategy": "composite", "seed": 1, "enable_delay_fault": True}
        )

        tests = client.get("/tests").json()
        worst = max(tests, key=lambda test: test["historical_failure_rate"])
        assert worst["historical_failure_rate"] > 0

        response = client.post(
            "/runs", json={"strategy": "failure_rate", "seed": 1, "enable_delay_fault": False}
        )
        assert response.json()["summary"]["failed"] == 0

        detail = client.get(f"/runs/{response.json()['run_id']}").json()
        assert detail["results"][0]["name"] == worst["name"]
        assert detail["results"][0]["passed"] == 1


def test_failure_diagnostics_recorded_for_failed_run(backend) -> None:
    with TestClient(backend.app) as client:
        response = client.post(
            "/runs", json={"strategy": "composite", "seed": 1, "enable_delay_fault": True}
        )
        assert response.json()["summary"]["failed"] > 0

        diagnostics = client.get("/diagnostics").json()
        failures = [record for record in diagnostics if record["event"] == "diagnostic.failure"]

        assert len(failures) > 0
        keys = {"test_name", "expected", "actual", "fault", "duration_seconds"}
        assert all(keys.issubset(failure["payload"]) for failure in failures)

        run_result = client.get(f"/runs/{response.json()['run_id']}").json()
        failed_names = {result["name"] for result in run_result["results"] if not result["passed"]}
        assert {failure["payload"]["test_name"] for failure in failures} == failed_names


def test_bus_mode_pipeline_runs_end_to_end_with_fakes(tmp_path, monkeypatch) -> None:
    history, logger, executor = build_components(tmp_path)
    monkeypatch.setattr(
        "vehicle_validation.automation.executor.can_channel_available", lambda channel: True
    )

    started = []
    stopped = []

    class RecordingSupervisor(FakeSupervisor):
        def start(self) -> None:
            started.append(True)
            super().start()

        def stop(self) -> None:
            stopped.append(True)
            super().stop()

    @contextmanager
    def fake_transport(_config):
        transport = FakeEcuTransport()
        yield transport

    executor.supervisor_factory = RecordingSupervisor
    executor.transport_factory = fake_transport

    test_run = executor.run(strategy_name="composite", seed=1, enable_delay_fault=False)

    assert test_run.metadata["mode"] == SOCKETCAN_MODE
    assert started == [True] and stopped == [True]
    assert len(test_run.results) == 3
    bus_safe_names = {
        definition.test_case.name for definition in scenario_catalog() if definition.bus_safe
    }
    assert {result.name for result in test_run.results} == bus_safe_names
    assert all(result.passed for result in test_run.results)
    assert history.run_details(test_run.run_id)["total"] == 3


def test_full_pipeline_across_multiple_runs(backend) -> None:
    with TestClient(backend.app) as client:
        for seed in range(3):
            response = client.post(
                "/runs", json={"strategy": "random", "seed": seed, "enable_delay_fault": False}
            )
            assert response.status_code == 200

        run_ids = _run_ids(client, count=3)
        runs = [client.get(f"/runs/{run_id}").json() for run_id in run_ids]

        assert [run["run_id"] for run in runs] == run_ids
        for index, run in enumerate(runs):
            assert run["metadata"]["strategy"] == "random"
            assert run["metadata"]["seed"] == str(2 - index)  # newest run listed first
            assert len(run["results"]) == 5

        statistics = client.get("/statistics").json()
        assert statistics["runs"] == 3
        assert statistics["passed"] == 15