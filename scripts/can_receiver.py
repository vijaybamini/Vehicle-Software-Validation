#!/usr/bin/env python3
"""Receive CAN frames from SocketCAN until interrupted."""

from __future__ import annotations

import argparse

import can


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Receive SocketCAN frames.")
    parser.add_argument("--channel", default="vcan0", help="SocketCAN channel")
    parser.add_argument(
        "--timeout",
        default=1.0,
        type=float,
        help="Receive timeout in seconds before printing an idle message",
    )
    return parser.parse_args()


def format_message(message: can.Message) -> str:
    payload = " ".join(f"{byte:02X}" for byte in message.data)
    return f"{message.timestamp:.6f} {message.arbitration_id:#05x} [{message.dlc}] {payload}"


def main() -> None:
    args = parse_args()
    print(f"listening on {args.channel}; press Ctrl+C to stop")

    with can.Bus(channel=args.channel, interface="socketcan") as bus:
        while True:
            message = bus.recv(timeout=args.timeout)
            if message is None:
                print("idle")
                continue
            print(format_message(message))


if __name__ == "__main__":
    main()
