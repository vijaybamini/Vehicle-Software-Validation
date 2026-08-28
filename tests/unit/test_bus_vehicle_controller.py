from collections import deque

from vehicle_validation.canbus.protocol import CanFrame, Gear, MessageId, VehicleState
from vehicle_validation.ecu.bms import BatteryManagementSystem
from vehicle_validation.ecu.motor import MotorController
from vehicle_validation.ecu.vcu import VehicleControlUnit
from vehicle_validation.vehicle.bus_controller import BusVehicleController


class FakeEcuTransport:
    """In-memory CAN transport that emulates the ECU process loop.

    Sending a `VCU_COMMAND` triggers the same publish sequence the real BMS /
    VCU / motor processes emit on the bus: a motor command, a VCU status, the
    motor status after the motor applied the command, and a fresh VCU status.
    """

    def __init__(self) -> None:
        self.bms = BatteryManagementSystem()
        self.vcu = VehicleControlUnit()
        self.motor = MotorController()
        self.sent: list[CanFrame] = []
        self._frames: deque[CanFrame] = deque(self.bms.publish())

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)
        if frame.arbitration_id != MessageId.VCU_COMMAND:
            return
        self.vcu.receive(frame)
        motor_command = self.vcu.motor_command()
        self._frames.append(motor_command)
        self._frames.append(self.vcu.publish())
        self._motor_react(motor_command)

    def receive(self, timeout: float = 0.1) -> CanFrame | None:
        return self._frames.popleft() if self._frames else None

    def close(self) -> None:
        pass

    def __enter__(self) -> "FakeEcuTransport":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def _motor_react(self, motor_command: CanFrame) -> None:
        self.motor.receive(motor_command)
        for _ in range(3):
            self.motor.tick()
        status = self.motor.publish()
        self._frames.append(status)
        self.vcu.receive(status)
        self._frames.append(self.vcu.motor_command())
        self._frames.append(self.vcu.publish())


def test_bus_start_reaches_ready_state() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())

    snapshot = vehicle.start()

    assert snapshot.state == VehicleState.READY


def test_bus_drive_sets_speed_and_torque() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())
    vehicle.start()

    snapshot = vehicle.drive(100, Gear.DRIVE)

    assert snapshot.state == VehicleState.DRIVE
    assert snapshot.torque_nm == 100
    assert snapshot.speed_deci_kph > 0


def test_bus_reverse_produces_negative_torque() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())
    vehicle.start()

    snapshot = vehicle.drive(80, Gear.REVERSE)

    assert snapshot.torque_nm == -80
    assert snapshot.gear == Gear.REVERSE


def test_bus_stop_returns_to_park() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())
    vehicle.start()
    vehicle.drive(100, Gear.DRIVE)

    snapshot = vehicle.stop()

    assert snapshot.gear == Gear.PARK


def test_bus_snapshot_falls_back_when_bus_silent() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())

    snapshot = vehicle.snapshot()

    assert snapshot.state == VehicleState.OFF
    assert snapshot.speed_deci_kph == 0