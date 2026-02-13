#!/usr/bin/env python3
import argparse
import re
from typing import List, Dict, Tuple

HEX8_RE = re.compile(r"\b[0-9a-fA-F]{8}\b")


def parse_amd_log_for_queues(log_file: str, target_pid: int) -> List[int]:
    queues = []
    pid_str = f"pid:{target_pid}"
    with open(log_file, "r", errors="ignore") as f:
        for line in f:
            if pid_str not in line:
                continue
            hwq_pos = line.find("HWq=0x")
            if hwq_pos == -1:
                continue
            try:
                addr_hex = line[hwq_pos:].split()[0].split("=")[1]
                addr = int(addr_hex, 16)
            except Exception:
                continue
            if addr not in queues:
                queues.append(addr)
    return queues


def parse_reg_dump_line(line: str) -> List[int]:
    if ":" not in line:
        return []
    _, tail = line.split(":", 1)
    return [int(x, 16) for x in HEX8_RE.findall(tail)]


def parse_hqds(lines: List[str]) -> List[Dict]:
    """Parse HQD debugfs lines into CP blocks. Each block has 'header', 'regs', 'active'."""
    blocks = []
    regs: List[int] = []
    header = ""
    in_cp_block = False

    def finish_block():
        nonlocal regs, header, in_cp_block
        if not in_cp_block or not regs:
            regs = []
            in_cp_block = False
            return
        active_val = regs[-1]
        blocks.append({"header": header.strip(), "regs": regs.copy(), "active": active_val != 0})
        regs = []
        in_cp_block = False

    for line in lines:
        if "CP Pipe" in line and "Queue" in line:
            finish_block()
            header = line
            in_cp_block = True
            regs = []
            continue

        if "HIQ" in line or "SDMA Engine" in line or "Device is stopped" in line:
            finish_block()
            continue

        if in_cp_block:
            regs.extend(parse_reg_dump_line(line))

    finish_block()
    return blocks


def match_active_queues(queue_addrs: List[int], blocks: List[Dict]) -> List[Tuple[int, bool]]:
    results = []
    for addr in queue_addrs:
        target = addr >> 8
        lo = target & 0xFFFFFFFF
        hi = (target >> 32) & 0xFFFFFFFF
        matched_active = False

        for blk in blocks:
            if not blk["active"]:
                continue
            regs = blk["regs"]
            for i in range(len(regs) - 1):
                if regs[i] == lo and regs[i + 1] == hi:
                    matched_active = True
                    break
            if matched_active:
                break

        results.append((addr, matched_active))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Parse KFD HQD debugfs (或 hqds.txt) 并可选地匹配 AMD 日志中的队列。"
    )
    parser.add_argument(
        "--hqds",
        default="/sys/kernel/debug/kfd/hqds",
        help="HQD 内容：debugfs 路径或已保存的文件，如 hqds.txt",
    )
    parser.add_argument("--log", help="可选：AMD_LOG_LEVEL=5 的日志，用于匹配 queue 地址")
    parser.add_argument("--pid", type=int, help="可选：目标 PID，与 --log 一起使用")
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="打印每块寄存器个数与最后一位(CP_HQD_ACTIVE)，便于排查",
    )
    parser.add_argument(
        "--gpu", type=int, default=None, metavar="N",
        help="仅解析指定 GPU 对应的 Inst（如 --gpu 0 只保留 Inst 0 的块；Workload 在 GPU 0 时用此可只看 GPU 0）",
    )
    args = parser.parse_args()

    with open(args.hqds, "r", errors="ignore") as f:
        blocks = parse_hqds(f.readlines())

    # GFX11 源码中 hqd_dump_v11 会 dump 57 个 reg，最后一个是 CP_HQD_ACTIVE。
    # 若本机驱动只 dump 56 个（不含 ACTIVE），则无法据此判断活跃，只能标为空闲。
    for b in blocks:
        n = len(b["regs"])
        b["_nregs"] = n
        if n >= 1:
            b["active"] = b["regs"][-1] != 0
        else:
            b["active"] = False
        # 56 个 reg 时最后一位是 CP_HQD_PQ_WPTR_HI 等，非 ACTIVE，不采用启发式避免误判
        b["_fallback"] = False

    if args.gpu is not None:
        inst = args.gpu
        blocks = [b for b in blocks if re.search(rf"\bInst\s+{inst}\s*,", b["header"])]
        print(f"仅解析 Inst {inst} (--gpu {args.gpu}): 共 {len(blocks)} 个 CP 块\n")

    active_blocks = sum(1 for b in blocks if b["active"])
    print(f"解析到 CP HQD 块: {len(blocks)}, 其中 active: {active_blocks}\n")

    # 仅解析 hqds：列出每个 CP 块及其活跃状态
    print("CP HQD 块（最后寄存器为 CP_HQD_ACTIVE，非0=活跃）:")
    for i, b in enumerate(blocks, 1):
        extra = ""
        if args.verbose and b["regs"]:
            extra = f"  [regs={b['_nregs']} 最后=0x{b['regs'][-1]:08x}]"
        print(f"  {i}. {b['header']} => {'活跃' if b['active'] else '空闲'}{extra}")
    if active_blocks == 0 and blocks:
        all_56 = all(b["_nregs"] == 56 for b in blocks)
        if all_56:
            print("说明：本机驱动只 dump 56 个寄存器，未包含 CP_HQD_ACTIVE，无法据此判断活跃。")
            print("      57 个 reg 只有在「已重新加载或重启并成功加载新 amdgpu 模块」后才会出现；")
            print("      若 DKMS 编译后未成功 reload，当前运行的仍是旧模块，会一直是 56。")
            print("      源码中需在 hqd_dump 追加 DUMP_REG(CP_HQD_ACTIVE)：")
            print("      GFX11 → amdgpu_amdkfd_gfx_v11.c 的 hqd_dump_v11()；")
            print("      Gfx942/MI308X → amdgpu_amdkfd_gfx_v12.c 的 hqd_dump_v12()。")
        else:
            print("提示：若全部为空闲，请用 --verbose 查看每块 reg 个数与最后一位；")
            print("      抓 hqds 时请确保 matmul_preempt（或目标进程）正在跑 GPU。")
    print()

    # 若提供 --log 和 --pid，再匹配 AMD 日志中的 queue
    if args.log and args.pid is not None:
        queue_addrs = parse_amd_log_for_queues(args.log, args.pid)
        if not queue_addrs:
            print("⚠️  未从 AMD 日志中找到 queue 地址（检查 pid 与 HWq=0x 行）")
            return
        matches = match_active_queues(queue_addrs, blocks)
        print("与 AMD 日志中的 queue 匹配:")
        for addr, active in matches:
            print(f"  Queue 0x{addr:016x} => active: {'是' if active else '否'}")


if __name__ == "__main__":
    main()
