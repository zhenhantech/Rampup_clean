# KFD Sysfs/Debugfs 命令：获取 MQD 与 HQD 及解析脚本

本文整理在 DOC_POC_stage1 中使用的**获取 MQD/HQD 的命令**及**后续解析脚本**，便于在 Rampup 中统一查阅。

---

## 一、获取 MQD 和 HQD 的命令

### 1. Debugfs 直接读（最常用）

| 内容 | 命令 |
|------|------|
| **MQD**（软件队列描述符） | `sudo cat /sys/kernel/debug/kfd/mqds` |
| **HQD**（硬件队列寄存器） | `sudo cat /sys/kernel/debug/kfd/hqds` |
| **RunList 状态** | `sudo cat /sys/kernel/debug/kfd/rls` |

前提：`/sys/kernel/debug` 已挂载（`sudo mount -t debugfs none /sys/kernel/debug`），且 KFD 已加载。

### 2. 程序化获取 Queue 信息（含 queue_id）

使用 **KFD_IOC_DBG_TRAP_GET_QUEUE_SNAPSHOT** 从内核直接拿到所有 queue 信息（含 queue_id、ring 地址、CWSR 等），无需解析 debugfs 文本。详见 DOC_POC_stage1 中的 **GET_QUEUE_SNAPSHOT_API_GUIDE.md**。

---

## 二、相关脚本与解析工具

脚本与工具位于 DOC_POC_stage1 的 `code/` 与 `code/poc_implementation/` 下。

### 1. 一次性读取并保存 MQD/HQD

- **`code/read_mqd_hqd.sh`**
  - 读取 `mqds`、`hqds`、`rls` 并保存到 `/tmp/kfd_*_时间戳.txt`
  - 做简单统计（Queue 条数、pipe/priority 等）
  - 需要 sudo

### 2. 周期 dump MQD/HQD

- **`code/record_mqd_hqd_loop.sh`**
  - 每隔 N 秒 dump 一次 `mqds` 和 `hqds` 到指定目录
  - 用法：`./record_mqd_hqd_loop.sh [间隔秒数] [输出目录]`
  - 默认 5 秒，输出到 `/tmp/mqd_hqd_logs_时间戳/`

- **`code/record_kfd_periodic.sh`**
  - 周期性 dump `hqds`、`mqds`、`rls` 三项
  - 用法：`sudo ./record_kfd_periodic.sh <log_folder> <sampling_interval>`
  - 例：`sudo ./record_kfd_periodic.sh /tmp/kfd_logs 5`
  - 输出结构：`log_folder/sample_1/`（含 hqds.txt、mqds.txt、rls.txt）、`sample_2/`、…；`session_info.txt` 记录首次采样时间、采样间隔等，便于后期恢复测试场景

### 3. HQD 解析脚本

| 脚本 | 路径 | 作用 |
|------|------|------|
| **parse_hqds_dump.py** | `code/parse_hqds_dump.py` | 解析 hqds dump，按 GPU 汇总 queue 使用；支持 CP_HQD_ACTIVE、PID、VMID 等 |
| **analyze_hqds_active.py** | `code/analyze_hqds_active.py` | 统计活跃 HQD：优先用 CP_HQD_ACTIVE，否则用 CP_HQD_PQ_BASE 非零判断；支持 `Inst X, CP Pipe Y, Queue Z` 格式 |
| **hqd_debug_parse.py** | `code/poc_implementation/hqd_debug_parse.py` | 解析 hqds 为 CP 块，可指定 `--hqds`、`--gpu`，输出 active 等；可从 stdin 读 |
| **monitor_hqds_gpu0.sh** | `code/poc_implementation/monitor_hqds_gpu0.sh` | 每秒读一次 hqds，只解析 GPU 0，用上面 Python 解析并打印 active 状态 |

**上述 HQD 解析脚本的使用参数：**

- **parse_hqds_dump.py**
  - `--input`, `-i`：输入 dump 文件（不指定则从 stdin 读）
  - `--output`, `-o`：输出汇总文件
  - 示例：`python3 parse_hqds_dump.py -i hqds_dump.txt -o hqds_summary.txt`；`sudo cat /sys/kernel/debug/kfd/hqds | python3 parse_hqds_dump.py`

- **analyze_hqds_active.py**
  - `--input-dir`, `-i`：**必填**，包含 `hqds_*.txt` 的目录
  - `--output`, `-o`：输出汇总文件（不指定则打印到 stdout）
  - 示例：`python3 analyze_hqds_active.py -i /path/to/hqds_dumps -o summary.csv`

- **hqd_debug_parse.py**
  - `--hqds`：HQD 来源（默认 `/sys/kernel/debug/kfd/hqds`），可为 debugfs 路径或已保存文件，也可用 `/dev/stdin` 从管道读
  - `--gpu`：只解析指定 GPU 的 Inst（如 `--gpu 0` 只解析 GPU 0）
  - `--log`：可选，AMD_LOG_LEVEL=5 的日志，用于按 queue 地址匹配
  - `--pid`：可选，目标 PID，需与 `--log` 一起用
  - `--verbose`, `-v`：打印每块寄存器个数与最后一位（CP_HQD_ACTIVE）
  - 示例：`python3 hqd_debug_parse.py --hqds /sys/kernel/debug/kfd/hqds --gpu 0 -v`；`python3 hqd_debug_parse.py --hqds hqds.txt --log amd.log --pid 12345`

- **monitor_hqds_gpu0.sh**
  - 用法：`sudo ./monitor_hqds_gpu0.sh [--verbose]` 或 `[-v]`（可选，传给内部 Python 做详细输出）
  - 环境变量：`INTERVAL` 采样间隔秒数（默认 1，如 `INTERVAL=2`）；`HQDS_PATH` 默认 `/sys/kernel/debug/kfd/hqds`
  - 退出：Ctrl+C

### 4. 其他相关脚本

- **`code/poc_implementation/build_and_test_hqd.sh`**：测试 hqds 可读性并跑 `hqd_debug_parse.py`
- **`code/poc_implementation/diagnose_queue_issue.sh`**：诊断时从 `mqds` 里按 PID 查队列信息
- **`code/poc_implementation/verify_queue_status.sh`**：用 `MQDS_FILE=/sys/kernel/debug/kfd/mqds` 校验队列状态
- **`code/poc_implementation/queue_finder.c`**：C 代码里读 `/sys/kernel/debug/kfd/hqds` 做解析

---

## 三、文档索引（命令与解析说明）

- **ARCH_Design_04_HQD信息获取完整指南.md**：MQD/HQD 命令、CP_HQD_ACTIVE 含义、Shell/Python/C 读取与解析示例（含 count_active_hqd.sh、hqd_reader.py、hqd_monitor.c 思路）
- **HQD_INSPECTION_GUIDE.md**：多种查看 HQD 的方法（debugfs、AMD_LOG_LEVEL、KFD Debug API、rocm-smi）及状态解析
- **GET_QUEUE_SNAPSHOT_API_GUIDE.md**：用 ioctl 获取 queue 信息（含 queue_id），替代 cat mqds/hqds
- **00_INDEX_POC_TOOLS_AND_DOCS.md**：整体工具与文档索引

以上文档均在：`.../amdgpudriver/doc/scheduler/DOC_POC_stage1/`。

---

## 四、快速用法示例

```bash
# 1. 获取并保存 MQD/HQD
cd .../DOC_POC_stage1/code
sudo ./read_mqd_hqd.sh

# 2. 周期 dump（另开终端，配合跑 DS 等）
./record_mqd_hqd_loop.sh 5 /tmp/my_mqd_hqd_logs

# 2b. 周期 dump hqds+mqds+rls（含 RunList）
sudo ./record_kfd_periodic.sh /tmp/kfd_logs 5

# 3. 解析已有 hqds dump，统计活跃 HQD
python3 analyze_hqds_active.py /path/to/hqds_dump.txt

# 4. 从 stdin 解析 hqds
sudo cat /sys/kernel/debug/kfd/hqds | python3 parse_hqds_dump.py

# 5. 只监控 GPU0 的 HQD active
cd poc_implementation && sudo ./monitor_hqds_gpu0.sh
```

---

## 五、小结

- **获取 MQD/HQD 的命令**：`sudo cat /sys/kernel/debug/kfd/mqds` 与 `sudo cat /sys/kernel/debug/kfd/hqds`。
- **解析脚本**集中在 DOC_POC_stage1 的 `code/` 和 `code/poc_implementation/` 下；完整说明见 **ARCH_Design_04_HQD信息获取完整指南.md** 与 **HQD_INSPECTION_GUIDE.md**。
