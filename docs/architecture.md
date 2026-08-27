# MVP architecture

The platform validates simulated electric-vehicle software before hardware is available.

```text
React dashboard -> FastAPI -> automation runner -> vehicle controller
                                                -> CAN transport -> ECUs
SQLite <------------------------------------------ test results / metrics
```

The default development transport is an in-process virtual CAN bus. On Linux the
same transport boundary supports `python-can` over SocketCAN (`vcan0`). This
keeps automated tests portable while providing a real virtual-network milestone.

## Decisions

- Python 3.11+, `python-can`, pytest, SQLite, FastAPI, React + TypeScript.
- Three intentionally small ECUs: BMS, VCU, and motor controller.
- Tests use vehicle-level actions; CAN encoding remains behind protocol and
  transport modules.
- Scheduling is a strategy interface backed by historical execution data.
- No physical hardware, ADB, packet capture, Docker, or distributed services in
  this MVP.
