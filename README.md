# Vehicle Software Validation

Vehicle Software Validation is an MVP platform for validating simulated
electric-vehicle control software before physical hardware is available. It
combines CAN simulation, ECU models, pytest automation, scheduling experiments,
historical result storage, a FastAPI service, and a React dashboard.

## Phase scope

The current target is phases 0 through 22 in
[docs/implementation-plan.md](docs/implementation-plan.md). Phases 23 and 24
are intentionally deferred as stretch work.

## Repository layout

- `src/vehicle_validation/`: Python package for CAN transport, ECU models,
  automation, schedulers, database access, and backend service code.
- `tests/`: Unit, integration, ECU, and functional validation tests.
- `frontend/`: React + TypeScript dashboard workspace.
- `experiments/`: Reproducible scheduler and fault-injection experiments.
- `config/`: Runtime and test configuration files.
- `docs/`: Architecture, protocol, implementation, and operator notes.
- `scripts/`: Local setup and developer utility scripts.
- `logs/`: Runtime logs, kept out of Git except for `.gitkeep`.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
