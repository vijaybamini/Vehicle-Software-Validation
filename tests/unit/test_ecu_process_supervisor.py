from vehicle_validation.canbus.transport import CanTransportConfig
from vehicle_validation.ecu.supervisor import EcuSupervisor, can_channel_available


def test_can_channel_available_returns_bool() -> None:
    assert isinstance(can_channel_available("definitely-not-a-real-can-channel"), bool)


def test_supervisor_uses_socketcan_defaults() -> None:
    supervisor = EcuSupervisor()

    assert supervisor.config == CanTransportConfig(interface="socketcan", channel="vcan0", bitrate=500000)
