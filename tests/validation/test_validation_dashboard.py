"""Level 9 - Dashboard.

Validates the backend/dashboard claims:
  - run lifecycle API (POST /runs, GET /runs, GET /runs/{id})
  - statistics and test catalog endpoints
  - scheduler comparison endpoint
  - vehicle status and runtime mode endpoints
  - diagnostics populated for failed runs (not just a sample)
  - live WebSocket streams: /ws/status and /ws/progress
"""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from vehicle_validation.backend import app as backend_app
from tests.validation.conftest import make_run

EVENT_TYPES = {"run.started", "run.completed", "test.started", "test.passed", "test.failed"}
SNAPSHOT_FIELDS = {
    "state",
    "gear",
    "speed_deci_kph",
    "torque_nm",
    "soc_percent",
    "battery_temperature_celsius",
    "motor_temperature_celsius",
    "fault",
}


def test_post_run_creates_and_persists_a_run(backend) -> None:
    with TestClient(backend.app) as client:
        response = client.post(
            "/runs", json={"strategy": "composite", "seed": 1, "enable_delay_fault": False}
        )

        assert response.status_code == 200
        payload = response.json()
        run_id = payload["run_id"]
        assert payload["summary"]["total"] == 5
        assert payload["summary"]["passed"] == 5
        assert payload["summary"]["failed"] == 0
        assert payload["metadata"]["strategy"] == "composite"
        assert payload["metadata"]["seed"] == "1"

        assert client.get("/runs").json()[0]["run_id"] == run_id

        detail = client.get(f"/runs/{run_id}").json()
        assert detail["metadata"]["strategy"] == "composite"
        assert detail["total"] == 5 and detail["failed"] == 0


def test_get_unknown_run_returns_404(backend) -> None:
    with TestClient(backend.app) as client:
        response = client.get("/runs/missing")

        assert response.status_code == 404


def test_list_runs_returns_newest_first(backend) -> None:
    with TestClient(backend.app) as client:
        history, _, _ = backend.history, backend.structured_logger, backend.executor
        history.save_run(make_run("older"))
        time.sleep(0.02)
        history.save_run(make_run("newer"))

        listing = client.get("/runs").json()

        assert [entry["run_id"] for entry in listing] == ["newer", "older"]


def test_statistics_endpoint_reflects_saved_runs(backend) -> None:
    with TestClient(backend.app) as client:
        history, _, _ = backend.history, backend.structured_logger, backend.executor
        history.save_run(make_run("r1", passed=2, failed=1))

        statistics = client.get("/statistics").json()

        assert statistics["runs"] == 1
        assert statistics["passed"] == 2
        assert statistics["failed"] == 1


def test_test_catalog_endpoint_exposes_scenarios(backend) -> None:
    with TestClient(backend.app) as client:
        tests = client.get("/tests").json()

        assert len(tests) == 5
        keys = {"name", "estimated_duration_seconds", "historical_failure_rate", "priority"}
        assert all(keys.issubset(test) for test in tests)


def test_scheduler_comparison_returns_four_strategies(backend) -> None:
    with TestClient(backend.app) as client:
        comparison = client.get("/scheduler/comparison", params={"seed": 7}).json()

        assert len(comparison) == 4
        assert {row["strategy"] for row in comparison} == {
            "composite",
            "failure_rate",
            "random",
            "shortest_processing_time",
        }
        assert all(len(row["ordered_tests"]) == 5 for row in comparison)
        assert all(row["seed"] == 7 for row in comparison)


def test_vehicle_status_snapshot(backend) -> None:
    with TestClient(backend.app) as client:
        status = client.get("/vehicle/status").json()

        assert SNAPSHOT_FIELDS == set(status.keys())


def test_runtime_can_reports_mode_consistent_with_availability(backend) -> None:
    with TestClient(backend.app) as client:
        runtime = client.get("/runtime/can", params={"channel": "vcan0"}).json()

        assert runtime["channel"] == "vcan0"
        assert runtime["socketcan_available"] in (True, False)
        assert runtime["mode"] == (
            "socketcan-processes" if runtime["socketcan_available"] else "in-process-fallback"
        )


def test_diagnostics_defaults_to_sample_when_store_empty(backend) -> None:
    with TestClient(backend.app) as client:
        diagnostics = client.get("/diagnostics").json()

        assert len(diagnostics) == 1
        assert diagnostics[0]["event"] == "diagnostic.sample"


def test_diagnostics_reflect_real_failed_run(backend) -> None:
    with TestClient(backend.app) as client:
        response = client.post(
            "/runs", json={"strategy": "composite", "seed": 1, "enable_delay_fault": True}
        )
        payload = response.json()
        assert payload["summary"]["failed"] > 0

        diagnostics = client.get("/diagnostics").json()

        assert len(diagnostics) >= 1
        assert diagnostics[0]["event"] != "diagnostic.sample"


def test_websocket_status_streams_snapshots(backend) -> None:
    with TestClient(backend.app) as client:
        with client.websocket_connect("/ws/status") as websocket:
            snapshot = websocket.receive_json()

            assert SNAPSHOT_FIELDS == set(snapshot.keys())
            websocket.close()


def test_websocket_progress_delivers_events(backend) -> None:
    with TestClient(backend.app) as client:
        with client.websocket_connect("/ws/progress") as websocket:
            time.sleep(0.05)  # allow the server to subscribe
            backend_app.hub.publish({"event": "run.started", "payload": {"run_id": "stream-run"}})
            backend_app.hub.publish({"event": "test.passed", "payload": {"run_id": "stream-run", "name": "n/a"}})
            backend_app.hub.publish(
                {"event": "run.completed", "payload": {"run_id": "stream-run", "summary": {"total": 1, "passed": 1, "failed": 0}}}
            )

            started = websocket.receive_json()
            assert started["event"] == "run.started"
            assert started["payload"]["run_id"] == "stream-run"
            assert websocket.receive_json()["event"] == "test.passed"
            completed = websocket.receive_json()
            assert completed["event"] == "run.completed"
            assert completed["payload"]["run_id"] == "stream-run"


def test_websocket_progress_full_run_event_stream(backend) -> None:
    with TestClient(backend.app) as client:
        with client.websocket_connect("/ws/progress") as websocket:
            time.sleep(0.05)  # allow the server to subscribe

            def run_in_thread() -> None:
                backend.executor.run(
                    strategy_name="composite",
                    seed=1,
                    enable_delay_fault=False,
                    on_event=backend_app.hub.publish,
                )

            threading.Thread(target=run_in_thread, daemon=True).start()

            events = []
            while True:
                events.append(websocket.receive_json())
                if events[-1]["event"] == "run.completed" or len(events) >= 50:
                    break

            event_types = [event["event"] for event in events]
            assert event_types[0] == "run.started"
            assert event_types[-1] == "run.completed"
            assert all(event in EVENT_TYPES for event in event_types)

            first_payload = events[0]["payload"]
            final_payload = events[-1]["payload"]
            assert final_payload["run_id"] == first_payload["run_id"]
            assert final_payload["run_id"] != ""
            assert final_payload["summary"]["total"] == 5
            assert final_payload["summary"]["passed"] == 5
            assert backend.history.run_details(first_payload["run_id"]) is not None