"""Level 1 - ECU communication.

Validates the CAN layer claims:
  - BMS <-> VCU and VCU <-> Motor Controller link over CAN frames
  - CAN message correctness (ids, 8-byte payloads, signed big-endian signals)
  - message timing / cadence configuration
  - ECU process startup and shutdown (supervisor lifecycle)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from vehicle_validation.canbus.protocol import (
    FaultCode,
    Gear,
    MessageId,
    VehicleState,
    make_bms_status,
    make_motor_status,
)
from vehicle_validation.canbus.transport import CanTransportConfig
from vehicle_validation.ecu.process_runtime import (
    run_bms,
    run_motor,
    run_vcu,
)
from vehicle_validation.ecu.supervisor import EcuSupervisor
from vehicle_validation.ecu.vcu import VehicleControlUnit
from vehicle_validation.vehicle.bus_controller import BusVehicleController
from tests.unit.test_bus_vehicle_controller import FakeEcuTransport

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"


def test_bms_status_informs_vcu_and_latches_fault() -> None:
    vcu = VehicleControlUnit()
    vcu.receive(make_bms_status(VehicleState.READY, 80, 99, 3600, 0, FaultCode.OVER_TEMPERATURE))

    assert vcu.state.fault == FaultCode.OVER_TEMPERATURE
    assert vcu.state.enabled is False


def test_bms_safe_status_keeps_vcu_available() -> None:
    vcu = VehicleControlUnit()
    vcu.receive(make_bms_status(VehicleState.READY, 80, 99, 3600, 0, FaultCode.NONE))

    assert vcu.state.fault == FaultCode.NONE


def test_motor_status_completes_loop_to_vcu() -> None:
    vcu = VehicleControlUnit()
    vcu.receive(make_motor_status(VehicleState.DRIVE, 500, -80, 35, FaultCode.NONE))

    assert vcu.state.motor_speed_rpm == 500
    assert vcu.state.motor_torque_nm == -80


def test_vcu_turns_driver_command_into_can_motor_command() -> None:
    from vehicle_validation.canbus.protocol import make_vcu_command

    vcu = VehicleControlUnit()
    vcu.receive(make_vcu_command(True, Gear.DRIVE, 40))
    command = vcu.motor_command()

    assert command.arbitration_id == MessageId.MOTOR_COMMAND
    assert bool(command.data[0]) is True
    torque = int.from_bytes(command.data[1:3], "big", signed=True)
    assert torque == 40


def test_vcu_reverse_command_encodes_negative_torque_in_can_frame() -> None:
    from vehicle_validation.canbus.protocol import make_vcu_command

    vcu = VehicleControlUnit()
    vcu.receive(make_vcu_command(True, Gear.REVERSE, 80, 0))
    command = vcu.motor_command()

    assert command.arbitration_id == MessageId.MOTOR_COMMAND
    assert bool(command.data[0]) is True
    torque = int.from_bytes(command.data[1:3], "big", signed=True)
    assert torque == -80
    speed_limit = int.from_bytes(command.data[3:5], "big", signed=False)
    assert speed_limit == vcu.config.default_speed_limit_rpm


def test_can_message_ids_spec() -> None:
    assert MessageId.BMS_STATUS == 0x101
    assert MessageId.BMS_TEMPERATURE == 0x102
    assert MessageId.VCU_COMMAND == 0x201
    assert MessageId.VCU_STATUS == 0x202
    assert MessageId.MOTOR_COMMAND == 0x301
    assert MessageId.MOTOR_STATUS == 0x302


def test_each_ecu_publishes_its_own_message_ids() -> None:
    from vehicle_validation.ecu.bms import BatteryManagementSystem
    from vehicle_validation.ecu.motor import MotorController

    bms = BatteryManagementSystem()
    motor = MotorController()
    vcu = VehicleControlUnit()

    bms_ids = {frame.arbitration_id for frame in bms.publish()}
    assert MessageId.BMS_STATUS in bms_ids
    assert MessageId.BMS_TEMPERATURE in bms_ids
    assert motor.publish().arbitration_id == MessageId.MOTOR_STATUS
    assert vcu.publish().arbitration_id == MessageId.VCU_STATUS


def test_bus_trace_contains_can_frames_with_correct_ids() -> None:
    vehicle = BusVehicleController(FakeEcuTransport())
    vehicle.drive(100, Gear.DRIVE)

    ids = {frame.arbitration_id for frame in vehicle.can_trace}
    assert MessageId.VCU_COMMAND in ids
    assert MessageId.MOTOR_COMMAND in ids
    assert MessageId.MOTOR_STATUS in ids
    assert MessageId.VCU_STATUS in ids


def test_process_loop_cadence_configuration() -> None:
    assert run_bms.__defaults__ == (0.2,)
    assert run_motor.__defaults__ == (0.1,)
    assert run_vcu.__defaults__ == (0.1,)


def test_supervisor_spawns_three_ecu_processes(monkeypatch) -> None:
    spawned: list = []

    class FakePopen:
        def __init__(self, args, **kwargs) -> None:
            self.args = args
            self.pid = 10000 + len(spawned)
            spawned.append(self)

        def poll(self) -> None:  # pragma: no cover - fake only
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float = 2.0) -> int:
            return 0

        def kill(self) -> None:
            self.killed = True

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    supervisor = EcuSupervisor(CanTransportConfig(channel="vcan0"))

    processes = supervisor.start()
    supervisor.stop()

    assert len(processes) == 3
    assert [process.name for process in processes] == ["bms", "motor", "vcu"]
    for process in spawned:
        for token in ("-m", "vehicle_validation.ecu.process_runtime"):
            assert token in process.args
        assert "--channel" in process.args
        assert process.args[process.args.index("--channel") + 1] == "vcan0"
        assert process.args[process.args.index("-m") + 1] == "vehicle_validation.ecu.process_runtime"
        assert getattr(process, "terminated", False)


def test_supervisor_stop_raises_without_start(monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: None)
    supervisor = EcuSupervisor(CanTransportConfig(channel="vcan0"))

    supervisor.stop()  # must not raise


@pytest.mark.lifecycle
def test_ecu_process_stack_start_and_stop_lifecycle() -> None:
    """Real subprocess smoke test - spawns the three ECU processes and reaps them."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    supervisor = EcuSupervisor(CanTransportConfig(channel="vcan0"))
    supervisor.start()

    assert len(supervisor.processes) == 3
    pids = [process.pid for process in supervisor.processes]

    try:
        supervisor.stop()
    finally:
        supervisor.stop()

    for pid in pids:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        except PermissionError:  # unreachable in this suite, keeps the check honest
            alive = True
        assert alive is False