#!/bin/bash
# 每 1 秒读取 /sys/kernel/debug/kfd/hqds，仅解析 GPU 0 (Inst 0) 的 CP 块并输出 active 状态。
# 用法: sudo ./monitor_hqds_gpu0.sh [--verbose]
# 可选环境变量: INTERVAL=2 间隔秒数; HQDS_PATH=/path/to/hqds
# Ctrl+C 退出。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HQDS_PATH="${HQDS_PATH:-/sys/kernel/debug/kfd/hqds}"
INTERVAL="${INTERVAL:-1}"

VERBOSE=""
[[ "${1:-}" = "--verbose" || "${1:-}" = "-v" ]] && VERBOSE="--verbose"

while true; do
    printf "\n=== %s (GPU 0 only) ===\n" "$(date '+%Y-%m-%d %H:%M:%S')"
    if ! sudo cat "$HQDS_PATH" 2>/dev/null | python3 "$SCRIPT_DIR/hqd_debug_parse.py" --hqds /dev/stdin --gpu 0 $VERBOSE 2>/dev/null; then
        echo "读取 hqds 失败或解析出错（需 root 且 debugfs 已挂载）"
    fi
    sleep "$INTERVAL"
done
