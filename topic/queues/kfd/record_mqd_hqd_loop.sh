#!/bin/bash
# =============================================================================
# MQD/HQD periodic recorder
# - Dump /sys/kernel/debug/kfd/mqds and /sys/kernel/debug/kfd/hqds periodically
# - Designed to run in a second terminal while DeepSeek 3.2 is running
# =============================================================================

set -e

INTERVAL="${1:-5}"   # seconds
OUT_DIR="${2:-/tmp/mqd_hqd_logs_$(date +%Y%m%d_%H%M%S)}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[ERROR]${NC} $1"; }

if ! sudo -n true 2>/dev/null; then
    print_err "This script requires sudo access."
    echo "Please run with sudo or configure passwordless sudo."
    exit 1
fi

if [ ! -d /sys/kernel/debug/kfd ]; then
    print_err "/sys/kernel/debug/kfd not found"
    echo "Try: sudo mount -t debugfs none /sys/kernel/debug"
    exit 1
fi

mkdir -p "$OUT_DIR"
print_ok "Output directory: $OUT_DIR"
print_info "Interval: ${INTERVAL}s"
print_info "Press Ctrl+C to stop"
echo ""

idx=0
while true; do
    ts="$(date +%Y%m%d_%H%M%S)"
    mqd_file="$OUT_DIR/mqds_${ts}.txt"
    hqd_file="$OUT_DIR/hqds_${ts}.txt"

    sudo cat /sys/kernel/debug/kfd/mqds > "$mqd_file" 2>/dev/null || true
    sudo cat /sys/kernel/debug/kfd/hqds > "$hqd_file" 2>/dev/null || true

    idx=$((idx + 1))
    print_ok "Dump #${idx}: mqds=${mqd_file}, hqds=${hqd_file}"

    sleep "$INTERVAL"
done

