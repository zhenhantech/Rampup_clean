#!/usr/bin/env python3
"""
Analyze hqds dump files to count active HQDs.

Priority:
  1) If CP_HQD_ACTIVE label exists, use it (non-zero => active)
  2) Fallback: use non-zero CP_HQD_PQ_BASE (first two dwords after CP Pipe line)

Supports hqds dumps like:
  Node 2, gpu_id f7bc:
  Inst 0,  CP Pipe 0, Queue 1
    0000c914: 006a5000 00000000 ...
"""

import argparse
import os
import re
from collections import defaultdict

NODE_RE = re.compile(r'^Node\s+(\d+),\s*gpu_id\s+([0-9a-fA-F]+)\s*:\s*$')
CP_PIPE_RE = re.compile(r'^Inst\s+(\d+),\s*CP\s+Pipe\s+(\d+),\s*Queue\s+(\d+)')
HIQ_RE = re.compile(r'^\s*Inst\s+(\d+),\s*HIQ\s+on\s+MEC\s+(\d+)\s+Pipe\s+(\d+)\s+Queue\s+(\d+)')
ACTIVE_RE = re.compile(r'CP_HQD_ACTIVE\s*=\s*0x([0-9a-fA-F]+)', re.IGNORECASE)
HEX_LINE_RE = re.compile(r'^[0-9a-fA-F]{8}:\s+([0-9a-fA-F]{8})\s+([0-9a-fA-F]{8})')


def parse_hqds_file(path):
    per_node = defaultdict(lambda: {
        "total": 0,
        "active_by_flag": 0,
        "active_by_base": 0,
        "hiq": 0,
    })

    cur_node = None
    pending_cp = False
    saw_active_flag = False

    with open(path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = NODE_RE.match(line)
            if m:
                cur_node = int(m.group(1))
                continue

            # HIQ counts as a queue entry
            if HIQ_RE.match(line):
                if cur_node is not None:
                    per_node[cur_node]["total"] += 1
                    per_node[cur_node]["hiq"] += 1
                pending_cp = False
                continue

            m = CP_PIPE_RE.match(line)
            if m:
                if cur_node is not None:
                    per_node[cur_node]["total"] += 1
                pending_cp = True
                continue

            # If CP_HQD_ACTIVE label exists, use it
            m = ACTIVE_RE.search(line)
            if m and cur_node is not None:
                saw_active_flag = True
                if int(m.group(1), 16) != 0:
                    per_node[cur_node]["active_by_flag"] += 1
                pending_cp = False
                continue

            # Fallback: first hex line after CP Pipe indicates PQ_BASE
            if pending_cp:
                m = HEX_LINE_RE.match(line)
                if m and cur_node is not None:
                    base_lo = m.group(1)
                    base_hi = m.group(2)
                    if base_lo != "00000000" or base_hi != "00000000":
                        per_node[cur_node]["active_by_base"] += 1
                    pending_cp = False

    return per_node, saw_active_flag


def format_single_file_summary(per_node, saw_flag):
    """Format summary for one hqds file."""
    total = sum(v["total"] for v in per_node.values())
    hiq = sum(v["hiq"] for v in per_node.values())
    active_flag = sum(v["active_by_flag"] for v in per_node.values())
    active_base = sum(v["active_by_base"] for v in per_node.values())
    lines = [
        "HQD active summary (single file)",
        f"  total HQDs: {total}, HIQ: {hiq}",
        f"  active (by CP_HQD_ACTIVE): {active_flag if saw_flag else 'N/A'}",
        f"  active (by PQ_BASE non-zero): {active_base}",
        "",
        "  Per-node:",
    ]
    for n in sorted(per_node.keys()):
        v = per_node[n]
        lines.append(f"    Node {n}: total={v['total']}, hiq={v['hiq']}, active_by_flag={v['active_by_flag']}, active_by_base={v['active_by_base']}")
    return "\n".join(lines)


def summarize_directory(input_dir):
    hqds_files = sorted([f for f in os.listdir(input_dir) if f.startswith("hqds_") and f.endswith(".txt")])
    if not hqds_files:
        raise SystemExit("No hqds_*.txt files found.")

    lines = []
    lines.append("DS3.2 HQD active summary")
    lines.append("timestamp, total_hqds, hiq_count, active_by_flag, active_by_base, per_node_totals, per_node_active_base")

    for fname in hqds_files:
        ts = fname.replace("hqds_", "").replace(".txt", "")
        per_node, saw_flag = parse_hqds_file(os.path.join(input_dir, fname))

        total = sum(v["total"] for v in per_node.values())
        hiq = sum(v["hiq"] for v in per_node.values())
        active_flag = sum(v["active_by_flag"] for v in per_node.values())
        active_base = sum(v["active_by_base"] for v in per_node.values())

        per_node_totals = ";".join([f"Node{n}:{per_node[n]['total']}" for n in sorted(per_node.keys())])
        per_node_active_base = ";".join([f"Node{n}:{per_node[n]['active_by_base']}" for n in sorted(per_node.keys())])

        lines.append(
            f"{ts}, {total}, {hiq}, {active_flag if saw_flag else 'NA'}, "
            f"{active_base}, {per_node_totals}, {per_node_active_base}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze HQD dumps and count active HQDs")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Single hqds dump file, or directory containing hqds_*.txt",
    )
    parser.add_argument("--output", "-o", help="Output summary file")
    args = parser.parse_args()

    path = args.input
    if not os.path.exists(path):
        raise SystemExit(f"No such file or directory: {path}")

    if os.path.isfile(path):
        per_node, saw_flag = parse_hqds_file(path)
        summary = format_single_file_summary(per_node, saw_flag)
    else:
        summary = summarize_directory(path)

    if args.output:
        with open(args.output, "w") as f:
            f.write(summary + "\n")
    else:
        print(summary)


if __name__ == "__main__":
    main()

