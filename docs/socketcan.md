# SocketCAN and vcan0

Phase 2 uses Linux SocketCAN with a virtual CAN interface named `vcan0`.

## Create vcan0

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
ip link show vcan0
```

If `vcan0` already exists, `ip link add` may print `File exists`. That is safe;
continue with `sudo ip link set up vcan0`.

## Send and receive

Open one terminal for the receiver:

```bash
python scripts/can_receiver.py --channel vcan0
```

Open another terminal for the sender:

```bash
python scripts/can_sender.py --channel vcan0 --arbitration-id 0x101 --data 01 64 00 00 00 00 00 00
```

The sender transmits one standard CAN frame. The receiver prints frames until
you stop it with `Ctrl+C`.
