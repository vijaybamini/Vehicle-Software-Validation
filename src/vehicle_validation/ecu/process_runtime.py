"""Long-running ECU process entrypoints over a CAN transport."""

from __future__ import annotations

import argparse
import signal
import time
from dataclasses import dataclass

from vehicle_validation.canbus.protocol import Gear, MessageId, make_vcu_command
from vehicle_validation.canbus.transport import CanTransportConfig, PythonCanTransport
from vehicle_validation.ecu.bms import BatteryManagementSystem
from vehicle_validation.ecu.motor import MotorController
from vehicle_validation.ecu.vcu import VehicleControlUnit


@dataclass
class ProcessRuntime:
    running: bool = True

    def stop(self, *_args: object) -> None:
        self.running = False


def install_signal_handlers(runtime: ProcessRuntime) -> None:
    signal.signal(signal.SIGINT, runtime.stop)
    signal.signal(signal.SIGTERM, runtime.stop)


def run_bms(config: CanTransportConfig, interval_seconds: float = 0.2) -> None:
    runtime = ProcessRuntime()
    install_signal_handlers(runtime)
    bms = BatteryManagementSystem()
    with PythonCanTransport(config) as transport:
        while runtime.running:
            for frame in bms.publish():
                transport.send(frame)
            time.sleep(interval_seconds)


def run_motor(config: CanTransportConfig, interval_seconds: float = 0.1) -> None:
    runtime = ProcessRuntime()
    install_signal_handlers(runtime)
    motor = MotorController()
    with PythonCanTransport(config) as transport:
        while runtime.running:
            frame = transport.receive(timeout=interval_seconds)
            if frame is not None:
                motor.receive(frame)
            motor.tick()
            transport.send(motor.publish())


def run_vcu(config: CanTransportConfig, interval_seconds: float = 0.1) -> None:
    runtime = ProcessRuntime()
    install_signal_handlers(runtime)
    vcu = VehicleControlUnit()
    with PythonCanTransport(config) as transport:
        while runtime.running:
            frame = transport.receive(timeout=interval_seconds)
            if frame is not None:
                vcu.receive(frame)
                if frame.arbitration_id in {MessageId.VCU_COMMAND, MessageId.BMS_STATUS, MessageId.MOTOR_STATUS}:
                    transport.send(vcu.motor_command())
                    transport.send(vcu.publish())


def send_driver_command(
    config: CanTransportConfig,
    enable: bool,
    gear: Gear,
    torque_nm: int,
    regen_percent: int = 0,
) -> None:
    with PythonCanTransport(config) as transport:
        transport.send(make_vcu_command(enable, gear, torque_nm, regen_percent))


def config_from_args(args: argparse.Namespace) -> CanTransportConfig:
    return CanTransportConfig(interface=args.interface, channel=args.channel, bitrate=args.bitrate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one simulated ECU process over python-can.")
    parser.add_argument("ecu", choices=["bms", "motor", "vcu", "driver"])
    parser.add_argument("--interface", default="socketcan")
    parser.add_argument("--channel", default="vcan0")
    parser.add_argument("--bitrate", default=500000, type=int)
    parser.add_argument("--torque", default=100, type=int)
    parser.add_argument("--gear", default="drive", choices=["park", "reverse", "neutral", "drive"])
    parser.add_argument("--disable", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    if args.ecu == "bms":
        run_bms(config)
    elif args.ecu == "motor":
        run_motor(config)
    elif args.ecu == "vcu":
        run_vcu(config)
    else:
        send_driver_command(
            config,
            enable=not args.disable,
            gear=Gear[args.gear.upper()],
            torque_nm=args.torque,
        )


if __name__ == "__main__":
    main()
