#!/usr/bin/env bash
set -euo pipefail

CHANNEL="${1:-vcan0}"

if ! command -v ip >/dev/null 2>&1; then
  echo "The 'ip' command is required. Install iproute2 and try again." >&2
  exit 1
fi

sudo modprobe vcan

if ! ip link show "$CHANNEL" >/dev/null 2>&1; then
  sudo ip link add dev "$CHANNEL" type vcan
fi

sudo ip link set up "$CHANNEL"
ip link show "$CHANNEL"
