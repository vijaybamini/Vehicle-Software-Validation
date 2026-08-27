from collections.abc import Callable

import pytest

from vehicle_validation.ecu.bms import BatteryManagementSystem
from vehicle_validation.ecu.motor import MotorController
from vehicle_validation.ecu.vcu import VehicleControlUnit
from vehicle_validation.vehicle.controller import VehicleController


@pytest.fixture
def bms() -> BatteryManagementSystem:
    return BatteryManagementSystem()


@pytest.fixture
def motor() -> MotorController:
    return MotorController()


@pytest.fixture
def vcu() -> VehicleControlUnit:
    return VehicleControlUnit()


@pytest.fixture
def vehicle() -> VehicleController:
    return VehicleController()


@pytest.fixture
def vehicle_factory() -> Callable[[], VehicleController]:
    return VehicleController
