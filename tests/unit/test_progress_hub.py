import asyncio

from vehicle_validation.backend.progress import ProgressHub


def test_progress_hub_broadcasts_to_subscribers() -> None:
    hub = ProgressHub()
    received: list[dict] = []

    async def consume() -> None:
        queue = hub.subscribe()
        hub.publish({"event": "test.started"})
        received.append(await queue.get())

    asyncio.run(consume())

    assert received == [{"event": "test.started"}]


def test_progress_hub_delivers_when_bound_to_loop() -> None:
    hub = ProgressHub()
    received: list[dict] = []

    async def main() -> None:
        hub.bind(asyncio.get_running_loop())
        queue = hub.subscribe()
        hub.publish({"event": "run.completed"})
        received.append(await queue.get())

    asyncio.run(main())

    assert received == [{"event": "run.completed"}]


def test_progress_hub_stops_delivering_after_unsubscribe() -> None:
    hub = ProgressHub()
    received: list[dict] = []

    async def main() -> None:
        hub.bind(asyncio.get_running_loop())
        queue = hub.subscribe()
        hub.unsubscribe(queue)
        hub.publish({"event": "run.completed"})
        await asyncio.sleep(0.01)
        assert not received

    asyncio.run(main())


def test_progress_hub_copies_events_before_delivery() -> None:
    hub = ProgressHub()
    received: list[dict] = []
    published = {"event": "test.started", "payload": {"name": "drive"}}

    async def main() -> None:
        queue = hub.subscribe()
        hub.publish(published)
        received.append(await queue.get())

    asyncio.run(main())

    received[0]["payload"]["name"] = "mutated"

    assert published["payload"]["name"] == "drive"