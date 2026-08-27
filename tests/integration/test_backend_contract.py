from vehicle_validation.backend.app import (
    RunRequest,
    can_runtime_status,
    create_run,
    list_tests,
    scheduler_comparison,
    vehicle_status,
)


def test_backend_catalog_has_tests() -> None:
    assert len(list_tests()) >= 5


def test_create_run_executes_and_persists_suite() -> None:
    payload = create_run(RunRequest(strategy="composite", seed=3, enable_delay_fault=False))

    assert payload["summary"]["total"] >= 5
    assert payload["metadata"]["strategy"] == "composite"


def test_scheduler_comparison_returns_all_strategies() -> None:
    payload = scheduler_comparison(seed=1)

    assert {item["strategy"] for item in payload} == {
        "random",
        "shortest_processing_time",
        "failure_rate",
        "composite",
    }


def test_vehicle_status_contract() -> None:
    payload = vehicle_status()

    assert "state" in payload
    assert "soc_percent" in payload
    assert "fault" in payload


def test_can_runtime_status_contract() -> None:
    payload = can_runtime_status("not-real")

    assert payload["channel"] == "not-real"
    assert "socketcan_available" in payload
