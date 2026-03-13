#!/bin/bash
# =============================================================================
# KFD 周期性记录脚本：hqds、mqds、rls
# 参考：read_mqd_hqd.sh（一次性读取）、record_mqd_hqd_loop.sh（周期 dump）
#
# 用法: ./record_kfd_periodic.sh <log_folder> <sampling_interval>
#   或: sudo ./record_kfd_periodic.sh /tmp/kfd_logs 5
#
# 参数:
#   log_folder       - 输出目录，dump 文件将保存到此
#   sampling_interval - 采样间隔（秒）
#
# 输出结构:
#   log_folder/
#     session_info.txt    - 首次采样时创建，记录场景信息（时间、间隔等）
#     sample_1/
#       hqds.txt
#       mqds.txt
#       rls.txt
#     sample_2/
#       ...
# Ctrl+C 停止
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[ERROR]${NC} $1"; }

# 参数解析
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "用法: $0 <log_folder> <sampling_interval>"
    echo "  例: $0 /tmp/kfd_logs 5"
    exit 1
fi
LOG_FOLDER="$1"
SAMPLING_INTERVAL="$2"

# 校验 sampling_interval 为正整数
if ! [[ "$SAMPLING_INTERVAL" =~ ^[0-9]+$ ]] || [ "$SAMPLING_INTERVAL" -le 0 ]; then
    print_err "sampling_interval 必须为正整数（秒）"
    exit 1
fi

# 检查 sudo
if ! sudo -n true 2>/dev/null; then
    print_err "此脚本需要 sudo 权限"
    echo "请使用 sudo 运行或配置免密 sudo"
    exit 1
fi

# 检查 debugfs
if [ ! -d /sys/kernel/debug/kfd ]; then
    print_err "/sys/kernel/debug/kfd 不存在"
    echo "尝试: sudo mount -t debugfs none /sys/kernel/debug"
    exit 1
fi

# 创建输出目录
mkdir -p "$LOG_FOLDER"
print_ok "输出目录: $LOG_FOLDER"
print_info "采样间隔: ${SAMPLING_INTERVAL}s"
print_info "按 Ctrl+C 停止"
echo ""

# Ctrl+C 时友好退出
trap 'echo ""; print_info "已停止"; exit 0' INT TERM

idx=0
while true; do
    idx=$((idx + 1))
    sample_dir="$LOG_FOLDER/sample_${idx}"
    mkdir -p "$sample_dir"

    # 首次采样时写入 session_info.txt
    if [ "$idx" -eq 1 ]; then
        first_ts="$(date +%Y-%m-%d\ %H:%M:%S)"
        first_ts_iso="$(date -Iseconds 2>/dev/null || echo "$first_ts")"
        {
            echo "first_sample_time=$first_ts"
            echo "first_sample_time_iso=$first_ts_iso"
            echo "sampling_interval_sec=$SAMPLING_INTERVAL"
            echo "log_folder=$LOG_FOLDER"
            echo "command=$0 $LOG_FOLDER $SAMPLING_INTERVAL"
            echo "hostname=$(hostname 2>/dev/null || echo 'unknown')"
        } > "$LOG_FOLDER/session_info.txt"
    fi

    hqd_file="$sample_dir/hqds.txt"
    mqd_file="$sample_dir/mqds.txt"
    rls_file="$sample_dir/rls.txt"

    sudo cat /sys/kernel/debug/kfd/hqds > "$hqd_file" 2>/dev/null || true
    sudo cat /sys/kernel/debug/kfd/mqds > "$mqd_file" 2>/dev/null || true
    sudo cat /sys/kernel/debug/kfd/rls  > "$rls_file" 2>/dev/null || true

    print_ok "Dump #${idx}: $sample_dir (hqds mqds rls)"

    sleep "$SAMPLING_INTERVAL"
done
