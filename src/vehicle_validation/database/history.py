"""SQLite-backed test history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from vehicle_validation.automation.results import TestResult, TestRun


SCHEMA = """
CREATE TABLE IF NOT EXISTS test_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    failure_reason TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES test_runs(run_id)
);
"""


class HistoryStore:
    def __init__(self, path: str | Path = "vehicle_validation.sqlite3") -> None:
        self.path = Path(path)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def save_run(self, test_run: TestRun) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO test_runs
                (run_id, started_at, metadata_json, total, passed, failed)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    test_run.run_id,
                    test_run.started_at,
                    json.dumps(test_run.metadata, sort_keys=True),
                    len(test_run.results),
                    test_run.passed,
                    test_run.failed,
                ),
            )
            connection.execute("DELETE FROM test_results WHERE run_id = ?", (test_run.run_id,))
            connection.executemany(
                """
                INSERT INTO test_results
                (run_id, name, passed, duration_seconds, failure_reason, steps_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [self._result_row(test_run.run_id, result) for result in test_run.results],
            )

    def list_runs(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM test_runs ORDER BY started_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def statistics(self) -> dict[str, float | int]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS runs,
                    COALESCE(SUM(total), 0) AS tests,
                    COALESCE(SUM(passed), 0) AS passed,
                    COALESCE(SUM(failed), 0) AS failed
                FROM test_runs
                """
            ).fetchone()
        tests = int(row["tests"])
        passed = int(row["passed"])
        return {
            "runs": int(row["runs"]),
            "tests": tests,
            "passed": passed,
            "failed": int(row["failed"]),
            "pass_rate": passed / tests if tests else 0.0,
        }

    def test_profiles(self) -> dict[str, dict[str, float | int]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    name,
                    COUNT(*) AS runs,
                    AVG(duration_seconds) AS average_duration_seconds,
                    AVG(CASE WHEN passed = 0 THEN 1.0 ELSE 0.0 END) AS failure_rate
                FROM test_results
                GROUP BY name
                """
            ).fetchall()
        return {
            row["name"]: {
                "runs": int(row["runs"]),
                "average_duration_seconds": float(row["average_duration_seconds"] or 0.0),
                "failure_rate": float(row["failure_rate"] or 0.0),
            }
            for row in rows
        }

    @staticmethod
    def _result_row(run_id: str, result: TestResult) -> tuple:
        return (
            run_id,
            result.name,
            int(result.passed),
            result.duration_seconds,
            result.failure_reason,
            json.dumps([step.__dict__ for step in result.steps], sort_keys=True),
        )
