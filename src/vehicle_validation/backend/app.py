"""FastAPI application for the validation platform."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from vehicle_validation.automation.diagnostics import build_failure_diagnostic
from vehicle_validation.automation.executor import ValidationExecutor
from vehicle_validation.automation.logging import StructuredLogger
from vehicle_validation.database.history import HistoryStore
from vehicle_validation.scheduler.experiments import evaluate_order
from vehicle_validation.scheduler.strategies import (
    CompositePriorityStrategy,
    FailureRateStrategy,
    RandomStrategy,
    ShortestProcessingTimeStrategy,
)
from vehicle_validation.vehicle.controller import VehicleController

app = FastAPI(title="Vehicle Software Validation", version="0.1.0")
history = HistoryStore()
vehicle = VehicleController()
structured_logger = StructuredLogger()
executor = ValidationExecutor(history, structured_logger)


class RunRequest(BaseModel):
    strategy: str = "composite"
    seed: int = 1
    enable_delay_fault: bool = False


@app.get("/tests")
def list_tests() -> list[dict]:
    return [test.__dict__ for test in executor.tests_with_history()]


@app.get("/runs")
def list_runs() -> list[dict]:
    return history.list_runs()


@app.post("/runs")
def create_run(request: RunRequest) -> dict:
    test_run = executor.run(
        strategy_name=request.strategy,
        seed=request.seed,
        enable_delay_fault=request.enable_delay_fault,
    )
    return test_run.to_dict()


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
    catalog = executor.tests_with_history()
    return [
        evaluate_order(strategy, catalog, seed, budget_seconds).__dict__
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


@app.get("/diagnostics")
def diagnostics() -> list[dict]:
    recent = structured_logger.read_recent()
    if recent:
        return recent

    sample = build_failure_diagnostic(
        test_name="motor_over_temperature_reaches_fault",
        expected="fault code over_temperature when motor exceeds threshold",
        actual="waiting for next fault run",
        fault=vehicle.snapshot().fault,
        duration_seconds=0.0,
        can_frames=[vehicle.motor.publish()],
    )
    return [{"event": "diagnostic.sample", "payload": sample.to_dict()}]


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(vehicle_status())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
