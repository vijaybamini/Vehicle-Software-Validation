from vehicle_validation.automation.collector import ResultCollector
from vehicle_validation.automation.framework import Scenario, ScenarioStep, require
from vehicle_validation.canbus.protocol import VehicleState


def test_collector_builds_structured_run() -> None:
    scenarios = [
        Scenario(
            "startup",
            (
                ScenarioStep(
                    "start",
                    lambda vehicle: vehicle.start(),
                    lambda snapshot: require(snapshot.state == VehicleState.READY, "ready expected"),
                ),
            ),
        )
    ]

    test_run = ResultCollector().run_scenarios(scenarios, run_id="demo", metadata={"seed": "1"})
    payload = test_run.to_dict()

    assert payload["run_id"] == "demo"
    assert payload["summary"] == {"total": 1, "passed": 1, "failed": 0}
    assert payload["metadata"] == {"seed": "1"}
    assert payload["results"][0]["name"] == "startup"
