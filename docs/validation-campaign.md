# Validation campaign

Last verified: 2026-08-28

This campaign validates the project claims feature by feature. The suite is
organized under `tests/validation/` and maps to the ten validation levels in
the project plan.

## Evidence summary

| Level | Area | Evidence |
| --- | --- | --- |
| 1 | ECU communication | BMS-to-VCU faults, VCU-to-motor commands, CAN IDs, payloads, bus traces, supervisor lifecycle |
| 2 | pytest automation framework | catalog discovery, fixtures, scenario execution, pass/fail diagnostics, cleanup |
| 3 | Functional testing | start, drive, reverse, stop, regen, SOC drop, low SOC, motor limits, invalid commands |
| 4 | Fault injection | delay holding/release, deterministic seeding, changed vehicle behavior, executor fault results, VCU communication timeout |
| 5 | Performance testing | bus-controller latency, timeout bounds, suite runtime budget, frame throughput |
| 6 | Database | run saving, newest-first retrieval, run details, failure preservation, scheduler profiles |
| 7 | Scheduler | random, SPT, failure-rate, composite scoring, seed reproducibility, historical influence |
| 8 | Experiment | repeated scheduler comparison, time-to-first-defect, budgeted defects, CSV/pandas round trip |
| 9 | Dashboard/API | `POST /runs`, run detail/history/statistics, diagnostics, scheduler comparison, status and progress WebSockets |
| 10 | Integration | full API pipeline, history-driven scheduling, failed-run diagnostics, bus-mode pipeline with fake transport |

## Current command

```bash
source .venv/bin/activate
pytest
npm --prefix frontend run build
```

Latest local result: `170 passed`.

## Remaining external validation

The automated suite proves the process-mode orchestration through fakes and
the in-process execution path end to end. A real SocketCAN run still requires
`vcan0` to exist on the host:

```bash
scripts/setup_vcan.sh vcan0
source .venv/bin/activate
PYTHONPATH=src scripts/run_ecu_stack.py --channel vcan0
```

When `vcan0` is available, `/runtime/can` should report
`socketcan-processes`, and non-fault `POST /runs` can use the bus-backed
controller for bus-safe scenarios.
