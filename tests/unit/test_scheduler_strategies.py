from vehicle_validation.scheduler.strategies import (
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
    TestCase,
    strategy_by_name,
)


def test_shortest_processing_time_orders_by_duration() -> None:
    tests = [TestCase("slow", 3.0), TestCase("fast", 1.0)]

    assert [test.name for test in ShortestProcessingTimeStrategy().order(tests)] == ["fast", "slow"]


def test_failure_rate_orders_by_likely_failure() -> None:
    tests = [TestCase("stable", 1.0, 0.1), TestCase("flaky", 1.0, 0.8)]

    assert [test.name for test in FailureRateStrategy().order(tests)] == ["flaky", "stable"]


def test_random_strategy_is_reproducible() -> None:
    tests = [TestCase(str(index)) for index in range(5)]

    first = RandomStrategy(seed=42).order(tests)
    second = RandomStrategy(seed=42).order(tests)

    assert first == second


def test_strategy_factory_rejects_unknown_name() -> None:
    try:
        strategy_by_name("unknown")
    except ValueError as exc:
        assert "unknown scheduler strategy" in str(exc)
    else:
        raise AssertionError("expected ValueError")
