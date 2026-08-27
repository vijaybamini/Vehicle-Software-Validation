from vehicle_validation.automation.faults import MessageDelayInjector
from vehicle_validation.canbus.protocol import Gear, MessageId, VehicleState, make_motor_status, make_vcu_status


def test_delay_injector_delays_matching_frame() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=2, seed=7)
    frame = make_motor_status(VehicleState.DRIVE, 1000, 80, 40)

    assert injector.inject(frame) == []
    assert injector.pending_count == 1
    assert injector.advance() == []
    assert injector.advance() == [frame]


def test_delay_injector_passes_non_matching_frame() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=2, seed=7)
    frame = make_vcu_status(VehicleState.READY, Gear.NEUTRAL, 0, 0)

    assert injector.inject(frame) == [frame]
    assert injector.pending_count == 0


def test_delay_injector_probability_can_disable_fault() -> None:
    injector = MessageDelayInjector({MessageId.MOTOR_STATUS}, delay_ticks=2, probability=0.0, seed=7)
    frame = make_motor_status(VehicleState.DRIVE, 1000, 80, 40)

    assert injector.inject(frame) == [frame]
