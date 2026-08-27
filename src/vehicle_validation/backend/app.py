"""FastAPI application for the validation platform."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from vehicle_validation.database.history import HistoryStore
from vehicle_validation.scheduler.experiments import evaluate_order
from vehicle_validation.scheduler.strategies import (
    CompositePriorityStrategy,
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
    TestCase,
)
from vehicle_validation.vehicle.controller import VehicleController

app = FastAPI(title="Vehicle Software Validation", version="0.1.0")
history = HistoryStore()
vehicle = VehicleController()


CATALOG = [
    TestCase("startup_reaches_ready_state", 0.5, 0.05, 0.2),
    TestCase("drive_command_produces_speed_and_torque", 1.2, 0.15, 0.3),
    TestCase("reverse_command_produces_negative_torque", 0.7, 0.20, 0.4),
    TestCase("low_soc_forces_vehicle_fault", 0.8, 0.75, 0.9),
    TestCase("motor_over_temperature_reaches_fault", 1.0, 0.65, 0.8),
]


@app.get("/tests")
def list_tests() -> list[dict]:
    return [test.__dict__ for test in CATALOG]


@app.get("/runs")
def list_runs() -> list[dict]:
    return history.list_runs()


@app.get("/statistics")
def statistics() -> dict:
    return history.statistics()


@app.get("/scheduler/comparison")
def scheduler_comparison(seed: int = 1, budget_seconds: float = 3.0) -> list[dict]:
    strategies = [
        RandomStrategy(seed),
        ShortestProcessingTimeStrategy(),
        FailureRateStrategy(),
        CompositePriorityStrategy(),
    ]
    return [
        evaluate_order(strategy, CATALOG, seed, budget_seconds).__dict__
        for strategy in strategies
    ]


@app.get("/vehicle/status")
def vehicle_status() -> dict:
    snapshot = vehicle.snapshot()
    return {
        "state": snapshot.state.name.lower(),
        "gear": snapshot.gear.name.lower(),
        "speed_deci_kph": snapshot.speed_deci_kph,
        "torque_nm": snapshot.torque_nm,
        "soc_percent": snapshot.soc_percent,
        "battery_temperature_celsius": snapshot.battery_temperature_celsius,
        "motor_temperature_celsius": snapshot.motor_temperature_celsius,
        "fault": snapshot.fault.name.lower(),
    }


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(vehicle_status())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
