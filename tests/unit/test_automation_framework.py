from vehicle_validation.automation.framework import Scenario, ScenarioRunner, ScenarioStep, require
from vehicle_validation.canbus.protocol import VehicleState


def test_scenario_runner_reports_pass() -> None:
    scenario = Scenario(
        "start vehicle",
        (
            ScenarioStep(
                "start",
                lambda vehicle: vehicle.start(),
                lambda snapshot: require(snapshot.state == VehicleState.READY, "vehicle should be ready"),
            ),
        ),
    )

    result = ScenarioRunner().run(scenario)

    assert result.passed
    assert result.steps[0].name == "start"


def test_scenario_runner_reports_failure_reason() -> None:
    scenario = Scenario(
        "bad expectation",
        (
            ScenarioStep(
                "start",
                lambda vehicle: vehicle.start(),
                lambda snapshot: require(snapshot.state == VehicleState.FAULT, "vehicle should fault"),
            ),
        ),
    )

    result = ScenarioRunner().run(scenario)

    assert not result.passed
    assert result.failure_reason == "vehicle should fault"
