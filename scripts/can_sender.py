#!/usr/bin/env python3
"""Send a single CAN frame over SocketCAN."""

from __future__ import annotations

import argparse

import can


def parse_byte(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFF:
        raise argparse.ArgumentTypeError(f"{value!r} is outside byte range 0..255")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send one SocketCAN frame.")
    parser.add_argument("--channel", default="vcan0", help="SocketCAN channel")
    parser.add_argument(
        "--arbitration-id",
        default="0x101",
        type=lambda value: int(value, 0),
        help="CAN arbitration ID, for example 0x101",
    )
    parser.add_argument(
        "--data",
        nargs="+",
        default=["0x01", "0x64", "0x00", "0x00", "0x00", "0x00", "0x00", "0x00"],
        type=parse_byte,
        help="Payload bytes in hex or decimal form",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    message = can.Message(
        arbitration_id=args.arbitration_id,
        data=args.data,
        is_extended_id=False,
    )

    with can.Bus(channel=args.channel, interface="socketcan") as bus:
        bus.send(message)

    payload = " ".join(f"{byte:02X}" for byte in message.data)
    print(f"sent {message.arbitration_id:#05x} [{message.dlc}] {payload}")


if __name__ == "__main__":
    main()
