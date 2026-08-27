from vehicle_validation.scheduler.experiments import evaluate_order
from vehicle_validation.scheduler.strategies import FailureRateStrategy, TestCase


def test_experiment_result_tracks_first_defect_and_budget() -> None:
    tests = [
        TestCase("stable", 5.0, 0.1),
        TestCase("defect", 1.0, 0.9),
    ]

    result = evaluate_order(FailureRateStrategy(), tests, seed=1, duration_budget_seconds=2.0)

    assert result.time_to_first_defect == 1.0
    assert result.defects_within_budget == 1
    assert result.ordered_tests[0] == "defect"
