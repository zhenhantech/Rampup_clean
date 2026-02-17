#!/usr/bin/env python3
"""
Parse /sys/kernel/debug/kfd/hqds dump and summarize per-GPU queue usage.

Usage:
  python3 parse_hqds_dump.py --input hqds_dump.txt --output hqds_summary.txt
  sudo cat /sys/kernel/debug/kfd/hqds | python3 parse_hqds_dump.py
"""

import argparse
import re
import sys
from collections import Counter, defaultdict


# GPU: "GPU 0", "gpu_id=123", or "Node 2, gpu_id f7bc:" (hex)
GPU_RE = re.compile(
    r'(?:GPU\s*\[?(\d+)\]?|gpu_id\s*[:=]\s*(\d+)|Node\s+(\d+),\s*gpu_id\s+([0-9a-fA-F]+))',
    re.IGNORECASE,
)
QUEUE_RE = re.compile(r'\bQueue\s*(\d+)', re.IGNORECASE)
ACTIVE_RE = re.compile(r'CP_HQD_ACTIVE\s*=\s*0x([0-9a-fA-F]+)')
# Hex register line, e.g. "0000c91c: 00000001" (last dword = CP_HQD_ACTIVE when no label)
HEX_LINE_RE = re.compile(r'^[0-9a-fA-F]{8}:\s*(?:[0-9a-fA-F]{8}\s*)+$', re.IGNORECASE)
PID_RE = re.compile(r'(?:\bPID\b\s*[:=]\s*(\d+)|\bpid\b\s*[:=]\s*(\d+))')
VMID_RE = re.compile(r'\bVMID\b\s*[:=]\s*(\d+)', re.IGNORECASE)


def _last_dword_from_hex_line(line):
    """Extract last hex dword from a line like '0000c91c: 00000001'."""
    parts = line.split(":", 1)
    if len(parts) != 2:
        return None
    hex_words = re.findall(r'[0-9a-fA-F]{8}', parts[1])
    return int(hex_words[-1], 16) if hex_words else None


def parse_lines(lines):
    queues = []
    current_gpu = None
    current = None

    def flush_current():
        nonlocal current
        if current:
            queues.append(current)
            current = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        gpu_m = GPU_RE.search(line)
        if gpu_m:
            flush_current()
            gpu_id = gpu_m.group(1) or gpu_m.group(2)
            if gpu_id is not None:
                current_gpu = int(gpu_id)
            elif gpu_m.group(3) is not None:
                current_gpu = int(gpu_m.group(3))
            elif gpu_m.group(4) is not None:
                current_gpu = int(gpu_m.group(4), 16)
            continue

        queue_m = QUEUE_RE.search(line)
        if queue_m:
            flush_current()
            current = {
                "gpu": current_gpu,
                "queue": int(queue_m.group(1)),
                "active": None,
                "pid": None,
                "vmid": None,
            }
            continue

        if current is None:
            continue

        active_m = ACTIVE_RE.search(line)
        if active_m:
            current["active"] = int(active_m.group(1), 16) != 0
            continue

        if HEX_LINE_RE.match(line):
            last_active_dword = _last_dword_from_hex_line(line)
            continue

        pid_m = PID_RE.search(line)
        if pid_m:
            pid = pid_m.group(1) or pid_m.group(2)
            if pid is not None:
                current["pid"] = int(pid)
            continue

        vmid_m = VMID_RE.search(line)
        if vmid_m:
            current["vmid"] = int(vmid_m.group(1))
            continue

    flush_current()
    return queues


def summarize(queues):
    per_gpu = defaultdict(lambda: {"total": 0, "active": 0})
    per_pid = Counter()
    per_vmid = Counter()

    for q in queues:
        gpu = q["gpu"]
        if gpu is not None:
            per_gpu[gpu]["total"] += 1
            if q["active"]:
                per_gpu[gpu]["active"] += 1
        if q["pid"] is not None:
            per_pid[q["pid"]] += 1
        if q["vmid"] is not None:
            per_vmid[q["vmid"]] += 1

    return per_gpu, per_pid, per_vmid


def format_summary(queues, per_gpu, per_pid, per_vmid):
    lines = []
    lines.append("HQD dump summary")
    lines.append(f"Total queues parsed: {len(queues)}")
    lines.append("")

    lines.append("Per-GPU queue counts:")
    for gpu in sorted(per_gpu.keys()):
        stats = per_gpu[gpu]
        lines.append(f"  GPU {gpu}: total={stats['total']}, active={stats['active']}")
    lines.append("")

    if per_pid:
        lines.append("Top PIDs (by queue count):")
        for pid, cnt in per_pid.most_common(10):
            lines.append(f"  pid {pid}: {cnt}")
        lines.append("")

    if per_vmid:
        lines.append("Top VMIDs (by queue count):")
        for vmid, cnt in per_vmid.most_common(10):
            lines.append(f"  vmid {vmid}: {cnt}")
        lines.append("")

    lines.append("Notes:")
    lines.append("  - If GPU ID is missing in dump, counts may be incomplete.")
    lines.append("  - ACTIVE is derived from CP_HQD_ACTIVE (non-zero = active).")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Parse KFD HQD dump")
    parser.add_argument("--input", "-i", help="Input dump file (default: stdin)")
    parser.add_argument("--output", "-o", help="Output summary file")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", errors="ignore") as f:
            queues = parse_lines(f)
    else:
        queues = parse_lines(sys.stdin)

    per_gpu, per_pid, per_vmid = summarize(queues)
    summary = format_summary(queues, per_gpu, per_pid, per_vmid)

    if args.output:
        with open(args.output, "w") as out:
            out.write(summary + "\n")
    else:
        print(summary)


if __name__ == "__main__":
    main()
    parser = argparse.ArgumentParser(description="Parse KFD HQD dump")
    parser.add_argument("--input", "-i", help="Input dump file (default: stdin)")
    parser.add_argument("--output", "-o", help="Output summary file")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", errors="ignore") as f:
            queues = parse_lines(f)
    else:
        queues = parse_lines(sys.stdin)

    per_gpu, per_pid, per_vmid = summarize(queues)
    summary = format_summary(queues, per_gpu, per_pid, per_vmid)

    if args.output:
        with open(args.output, "w") as out:
            out.write(summary + "\n")
    else:
        print(summary)


if __name__ == "__main__":
    main()

       queues = parse_lines(f)
    else:
        queues = parse_lines(sys.stdin)

    per_gpu, per_pid, per_vmid = summarize(queues)
    summary = format_summary(queues, per_gpu, per_pid, per_vmid)

    if args.output:
        with open(args.output, "w") as out:
            out.write(summary + "\n")
    else:
        print(summary)


if __name__ == "__main__":
    main()

ite(summary + "\n")
    else:
        print(summary)


if __name__ == "__main__":
    main()

