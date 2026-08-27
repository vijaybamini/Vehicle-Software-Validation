"""CAN transport adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import can

from vehicle_validation.canbus.protocol import CanFrame


class CanTransport(Protocol):
    def send(self, frame: CanFrame) -> None:
        ...

    def receive(self, timeout: float = 0.1) -> CanFrame | None:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class CanTransportConfig:
    interface: str = "socketcan"
    channel: str = "vcan0"
    bitrate: int = 500000


class PythonCanTransport:
    """`python-can` backed transport for SocketCAN or supported alternatives."""

    def __init__(self, config: CanTransportConfig | None = None) -> None:
        self.config = config or CanTransportConfig()
        self.bus = can.Bus(
            interface=self.config.interface,
            channel=self.config.channel,
            bitrate=self.config.bitrate,
        )

    def send(self, frame: CanFrame) -> None:
        message = can.Message(
            arbitration_id=frame.arbitration_id,
            data=frame.data,
            is_extended_id=False,
        )
        self.bus.send(message)

    def receive(self, timeout: float = 0.1) -> CanFrame | None:
        message = self.bus.recv(timeout=timeout)
        if message is None:
            return None
        return CanFrame(message.arbitration_id, bytes(message.data).ljust(8, b"\x00")[:8])

    def close(self) -> None:
        self.bus.shutdown()

    def __enter__(self) -> "PythonCanTransport":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
