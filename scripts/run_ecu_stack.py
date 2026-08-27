#!/usr/bin/env python3
"""Start BMS, VCU, and motor ECU processes."""

from __future__ import annotations

import argparse
import time

from vehicle_validation.canbus.transport import CanTransportConfig
from vehicle_validation.ecu.supervisor import EcuSupervisor, can_channel_available


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the simulated ECU process stack.")
    parser.add_argument("--interface", default="socketcan")
    parser.add_argument("--channel", default="vcan0")
    parser.add_argument("--bitrate", default=500000, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interface == "socketcan" and not can_channel_available(args.channel):
        raise SystemExit(
            f"{args.channel} is not available. Run scripts/setup_vcan.sh {args.channel} first."
        )

    supervisor = EcuSupervisor(CanTransportConfig(args.interface, args.channel, args.bitrate))
    processes = supervisor.start()
    for process in processes:
        print(f"{process.name} pid={process.pid}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        supervisor.stop()


if __name__ == "__main__":
    main()
