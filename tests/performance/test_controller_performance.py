from time import perf_counter

from vehicle_validation.vehicle.controller import VehicleController


def test_controller_handles_100_ticks_under_budget() -> None:
    vehicle = VehicleController()
    vehicle.start()
    start = perf_counter()

    for _ in range(100):
        vehicle.drive(80)
        vehicle.tick()

    assert perf_counter() - start < 1.0
