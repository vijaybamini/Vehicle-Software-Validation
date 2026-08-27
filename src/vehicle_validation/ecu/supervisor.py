"""Supervisor for independent ECU subprocesses."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

from vehicle_validation.canbus.transport import CanTransportConfig


@dataclass(frozen=True)
class EcuProcess:
    name: str
    pid: int


def can_channel_available(channel: str = "vcan0") -> bool:
    ip = shutil.which("ip")
    if ip is None:
        return False
    result = subprocess.run(
        [ip, "link", "show", channel],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class EcuSupervisor:
    def __init__(self, config: CanTransportConfig | None = None) -> None:
        self.config = config or CanTransportConfig()
        self.processes: list[subprocess.Popen] = []

    def start(self) -> list[EcuProcess]:
        for ecu in ("bms", "motor", "vcu"):
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "vehicle_validation.ecu.process_runtime",
                    ecu,
                    "--interface",
                    self.config.interface,
                    "--channel",
                    self.config.channel,
                    "--bitrate",
                    str(self.config.bitrate),
                ]
            )
            self.processes.append(process)
        time.sleep(0.2)
        return [EcuProcess(name, process.pid) for name, process in zip(("bms", "motor", "vcu"), self.processes)]

    def stop(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
        self.processes.clear()
