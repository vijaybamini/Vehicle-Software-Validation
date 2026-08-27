"""Failure diagnostics for validation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from vehicle_validation.canbus.protocol import CanFrame, FaultCode


@dataclass(frozen=True)
class CanTraceEntry:
    arbitration_id: str
    payload: str

    @classmethod
    def from_frame(cls, frame: CanFrame) -> "CanTraceEntry":
        return cls(
            arbitration_id=f"{frame.arbitration_id:#05x}",
            payload=" ".join(f"{byte:02X}" for byte in frame.data),
        )


@dataclass(frozen=True)
class FailureDiagnostic:
    test_name: str
    expected: str
    actual: str
    fault: FaultCode = FaultCode.NONE
    duration_seconds: float = 0.0
    can_trace: list[CanTraceEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["fault"] = self.fault.name.lower()
        return payload


def build_failure_diagnostic(
    test_name: str,
    expected: str,
    actual: str,
    fault: FaultCode,
    duration_seconds: float,
    can_frames: list[CanFrame] | None = None,
) -> FailureDiagnostic:
    return FailureDiagnostic(
        test_name=test_name,
        expected=expected,
        actual=actual,
        fault=fault,
        duration_seconds=duration_seconds,
        can_trace=[CanTraceEntry.from_frame(frame) for frame in can_frames or []],
    )
