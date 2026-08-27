# CAN protocol

The MVP uses standard 11-bit CAN identifiers and fixed 8-byte payloads. Multi-byte
numeric values are unsigned big-endian unless noted.

| ID | Name | Producer | Payload |
| --- | --- | --- | --- |
| `0x101` | `BMS_STATUS` | BMS | byte 0 state, byte 1 SOC %, byte 2 SOH %, bytes 3-4 pack voltage decivolts, bytes 5-6 current deciamps signed, byte 7 fault code |
| `0x102` | `BMS_TEMPERATURE` | BMS | byte 0 min C, byte 1 max C, byte 2 average C, byte 3 thermal state, bytes 4-7 reserved |
| `0x201` | `VCU_COMMAND` | VCU | byte 0 enable, byte 1 gear, bytes 2-3 torque request Nm signed, byte 4 regen %, bytes 5-7 reserved |
| `0x202` | `VCU_STATUS` | VCU | byte 0 state, byte 1 gear, bytes 2-3 speed kph deci-units, bytes 4-5 torque Nm signed, byte 6 fault code, byte 7 reserved |
| `0x301` | `MOTOR_COMMAND` | VCU | byte 0 enable, bytes 1-2 torque request Nm signed, bytes 3-4 speed limit rpm, bytes 5-7 reserved |
| `0x302` | `MOTOR_STATUS` | Motor | byte 0 state, bytes 1-2 speed rpm, bytes 3-4 torque Nm signed, byte 5 temperature C, byte 6 fault code, byte 7 reserved |

## Enumerations

Vehicle state:

- `0`: off
- `1`: ready
- `2`: drive
- `3`: fault

Thermal state:

- `0`: normal
- `1`: warm
- `2`: hot
- `3`: critical

Gear:

- `0`: park
- `1`: reverse
- `2`: neutral
- `3`: drive

Fault code:

- `0`: none
- `1`: low SOC
- `2`: over temperature
- `3`: over current
- `4`: communication timeout
- `5`: invalid command
