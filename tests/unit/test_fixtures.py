from vehicle_validation.canbus.protocol import VehicleState
from vehicle_validation.vehicle.controller import VehicleController


def test_vehicle_fixture_starts_ready(vehicle: VehicleController) -> None:
    snapshot = vehicle.start()

    assert snapshot.state == VehicleState.READY
