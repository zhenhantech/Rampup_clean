# HybridServe 后三页中文口播稿

> **对应 PPT：** `TechDay.pptx` 后三页  
> **口径：** 中文为主，专业词汇保留 English；面向互联网客户，重点讲 challenge、design idea、practice/results。

---

## Page 8 — Challenge: Low Utilization on Peak-Provisioned Inference GPUs

### 口播

接下来我们切到 **HybridServe** 这个 topic。先看它要解决的问题：**peak-provisioned inference GPUs** 的利用率偏低，以及由此带来的 **TCO** 压力。

在实际 AI 服务里，我们可以按 **SLA latency** 把 workload 分成两类。

第一类是 **Online workload**，也就是面向用户的实时服务，比如 chatbot、real-time LLM API、coding assistant 等。
这类业务对 **latency** 非常敏感，通常会关注 **TTFT** 和 **TPOT**。为了保证在线体验，GPU pool 往往会按峰值流量来配置，并预留 **SLA headroom** 应对 burst traffic。

第二类是 **Offline workload**，比如 model training / fine-tuning、offline evaluation、等。
这类任务更关注 throughput 和任务完成时间，对实时 latency 的要求相对宽松，通常可以排队，也可以在必要时让路。

真正的 challenge 在资源侧。
**Online** GPU 服务器 会有 “GPU 使用率较低”的问题。这主要是由于GPU服务器是按照峰值流量配备的，
但实际运行中会有请求到达不均匀、调度空泡，以及 **prefill / decode switching** 等问题，所以 **time-average utilization** 往往并不高。

NOTE: 右下角这个示意图表达的就是几个典型空档：没有 inference request、scheduling bubble，以及 prefill / decode 切换带来的 gap。

**Offline workload** 这边，为了避免影响 online 业务的 **latency**，通常不能直接和 online model 共用同一套 GPU server，而是采用独立的 GPU server 或 GPU pool 部署。

这样就形成了一个矛盾：online GPU 有空档，但 offline 为了不影响 online SLA，仍然需要单独的资源。结果是整体 **GPU utilization** 不高，**TCO** 也会被抬高。

所以后面的 POC 重点验证的是：能不能在不影响 **online SLA** 的前提下，让 offline workload 利用 online inference GPU 的空闲时间。

---

## Page 9 — The Hybrid Serve: Online-First & Queue Suspend/Resume

### 口播

为了解决前面提到的 utilization 和 TCO 问题，我们提出 **HybridServe** 这个方案。

这个方案的目标很明确：在满足 **online latency SLA** 的前提下，让 online 和 offline 共用同一套 GPU server，从而提高 GPU 利用率。

这是一个简单示意图。
- 平时 GPU 有空档时，offline model 可以运行；
- 当 online model 收到 Infer. Req#1 或 Req#2 时，HybridServe 会让 offline queue **suspend**，把 GPU 让给 online。
- 等 online inference 完成后，再让 offline queue **resume**，offline 继续执行之前的任务。

从这个流程图，可以看出Hybrid Serve三个设计原则。
第一，**Online-workload first**。只要 online model 有 inference request，online 的 **latency SLA** 就是最高优先级。

第二，**Opportunistic offline**。Offline model 不主动和 online 抢资源，而是在 online 没有压力、GPU 有空档的时候运行。

第三，**Queue-level suspend / resume**。当 online 需要 GPU 时，offline queue **suspend**；online 完成后，offline queue **resume**。

所以这套机制不是简单的 workload colocation，而是 **online-first GPU sharing**：online 始终优先，offline 只利用 **spare GPU time**。

---

## Page 10 — The Hybrid Serve: The Practice

### 口播

最后看 Hybrid Serve 的具体实现方案，以及测试效果。

这一页有两个重点。第一，**full compatible with existing AI model test scripts**；第二，复用 **driver** 和 **hardware native support**。也就是说，POC 不要求改现有 model test script，也不要求改 driver source，而是在现有能力之上增加一层 HybridServe coordination。

整体架构分四个组件。

第一是 **Model Wrapper**。它用于封装AI模型的启动脚本，
当模型启动时候，会把 model 的PID，服务类别(online/offline) 注册到 HybridServe daemon。
当模型运行时，会通知 online model 的 inference start / stop 状态。，

第二是 **HybridServe**。
这里包括 `hybridserve_daemon`、`HTTP server.py` 和 `hybridserve_cli （Command line interface）`。
Daemon 通过 HTTP 接收 model register 和 model status；CLI 负责下发 suspend / resume command。

第三是 **CWSR**，也就是 **Compute Wave Save/Restore**。它依赖 AMD 原生的 **KFD、firmware 和 GPU built-in support**，支持 queue-based control 和 wavefront-level save / restore，提供硬件支持的 queue suspend / resume。

第四是 **Configurations**，包括 HTTP IP、port、timing 等配置项。

从调用流程看，online model 开始 inference 时，会通过 wrapper 通知 HybridServe；HybridServe 根据 online 状态决定是否 suspend offline queue；online 完成后，再 resume offline queue。底层真正执行 queue suspend / resume 的能力来自 CWSR 和 KFD ioctl。

结果部分，目前测试配置是：online model 使用 **Llama2-7B，8 GPU**；offline model 使用 **BERT，8 GPU**。初步结果显示，对 online model 的影响较小：**TTFT 增加 4.3%**，**P99-TPOT 增加 5.2%**。这说明在当前 POC 条件下，HybridServe 可以在保持 online latency impact 较小的同时，让 offline workload 利用 GPU 空闲窗口运行。

总结一下，HybridServe 的价值在于：在 **online SLA first** 的前提下，把原本难以利用的 inference GPU idle time 转化为 offline 计算能力，从而提升 GPU utilization，并有机会降低整体 **TCO**。


## NOTE: CWSR details（客户 Q&A 备用）

下面内容不建议在主口播里主动展开；如果客户追问 **queue suspend / resume** 的底层机制，可以按问题选择性回答。

### 1. CWSR 是什么？

**CWSR** 全称是 **Compute Wave Save/Restore**。可以理解为 AMD GPU 栈里已有的一套 **compute wavefront 上下文保存和恢复机制**。

在 HybridServe 里，CWSR 的作用不是做上层调度，而是提供底层能力：当需要让 offline workload 让出 GPU 时，系统可以在 **GPU queue** 层面触发 suspend，把相关 wavefront / queue 状态保存下来；后续 online workload 结束后，再 resume offline queue，继续执行。

对客户可以这样解释：

> HybridServe 的策略在用户态，真正的 queue suspend / resume 依赖 AMD 原生的 KFD、firmware 和 GPU built-in support，也就是 CWSR 这条能力。

### 2. 为什么说是 queue-level？

HybridServe 不是 kill 掉 offline process，也不是让 offline job 从头重跑，而是对 offline workload 对应的 **GPU queue** 做 suspend / resume。

当前 POC 的控制粒度可以理解为：

- HybridServe daemon 维护 online / offline model 的状态。
- Offline model 对应的 queue 被识别为可让路对象。
- Online inference 开始时，对 offline queue 执行 suspend。
- Online inference 结束后，对之前 suspend 的 offline queue 执行 resume。

可以补一句：

> 这里的 queue-level 控制，比 process-level stop/start 更细，也更贴近 GPU 执行路径。

### 3. 是否需要改 driver？

当前 POC 口径是：**不需要改 driver source**。

原因是 POC 复用了现有 KFD debug / queue control 路径，底层能力来自：

- **KFD**
- **firmware**
- **GPU built-in support**
- **CWSR**
- KFD debug trap 相关 ioctl，例如 **`SUSPEND_QUEUES` / `RESUME_QUEUES`**

对外可以说：

> POC 阶段我们复用现有 ROCm / KFD / GPU 能力，不要求客户修改 driver source。未来如果要产品化、进一步降低 latency 或简化授权路径，可以再考虑 driver 层优化。

### 4. Suspend / resume 具体做了什么？

简化理解：

- **Suspend**：让指定 offline GPU queue 暂停继续占用 GPU 执行资源，并保存必要的执行上下文。
- **Resume**：online workload 压力下降后，恢复之前被暂停的 offline queue，使 offline job 继续执行。

更技术一点：

> CWSR 支持 **wavefront-level save / restore**，KFD 提供 **queue-based control**。HybridServe 的策略层决定“什么时候 suspend / resume 哪些 offline queue”，底层执行由 KFD / CWSR 完成。

### 5. 和普通进程暂停有什么区别？

这不是简单的 Linux process `stop / continue`。

区别是：

- HybridServe 关注的是 **GPU queue**，不是只暂停 CPU process。
- Offline process 仍然是同一个 job，不是 kill / restart。
- 目标是让 GPU 执行资源先服务 online workload，同时保留 offline job 的继续执行能力。

对客户可以说：

> Offline workload 不是被杀掉，也不是从头重跑；它是在 GPU queue 层面让出资源，后续再继续。

### 6. 跨进程时有什么注意点？

Online / offline 通常是不同进程，跨进程 suspend / resume 需要明确：

- 哪个进程的哪个 queue 可以被 suspend；
- 谁有权限 suspend 目标 queue；
- 多 GPU、多 queue 场景下 queue 的身份要能唯一识别。

实现上通常需要维护类似 **`(pid, gpu_id, queue_id)`** 的注册表。这样可以避免只看 `queue_id` 时跨进程冲突。

当前 POC 里，这部分由 HybridServe / daemon 维护；底层调用仍走 KFD 能力。

### 7. 安全和权限怎么解释？

因为 suspend / resume 会影响另一个进程的 GPU queue，所以底层通常需要调试或授权关系。当前 POC 可以把它描述为受控测试环境下的能力验证。

更稳妥的客户口径：

> POC 重点验证 online-first sharing 的可行性；生产化时，需要把授权、租户隔离、容器 PID 映射、多 GPU queue 管理等纳入产品设计。

### 8. 和 vLLM / continuous batching 的关系？

CWSR / queue suspend 不是替代 vLLM 这类 serving framework 的内部调度。

关系是：

- vLLM / framework 负责单个 serving workload 内部的 batching、prefill/decode 调度。
- HybridServe 负责 **online workload 和 offline workload 之间** 的 GPU 共享策略。
- CWSR 提供底层 queue suspend / resume 能力。

一句话：

> Framework scheduler 管 model serving 内部效率；HybridServe 管 online / offline 之间的 GPU 让路和恢复。

### 9. 客户追问 latency 时怎么答？

不要承诺固定 suspend / resume latency。

建议口径：

> Suspend / resume latency 取决于 GPU、driver path、queue 状态、当前是否有在途 kernel 等因素。POC 里我们不单独承诺一个固定数值，而是从端到端效果评估：online SLA 是否在 agreed bounds 内、offline job 是否能稳定恢复完成。

如果客户继续追问：

> 后续 joint POC 可以把 suspend / resume overhead、TTFT、TPOT、P99 latency、offline completion time 都纳入测试指标。

### 10. 一句话总结

> HybridServe 决定“什么时候让 offline 让路”；CWSR / KFD 提供“怎么在 GPU queue 层面 suspend 和 resume”的底层能力。
