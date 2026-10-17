# 西电超算 · GPU 切换手册（完整速查版）

> 调度系统：景行 JH Unischeduler V6.6
> 提交命令：`jsub`（脚本内用 `#JSUB` 指令，**严禁用 SLURM/SGE/PBS 语法**）
> 本手册按平台"集群状态"页面的节点组截图整理；**节点组名以 `jhostgroup` 实际输出为准**，队列名以 `jqueues -u $USER` 为准。

---

## 0. 核心原理（30 秒看懂怎么"切换显卡"）

切换显卡 = 在 `jsub` 里换三个东西：

| 换什么 | 参数 | 说明 |
|---|---|---|
| 队列（决定卡型） | `-q <队列名>` | `gpu_4090` / `gpu_a800` / `gpu_h800` … |
| 节点组（锁卡型） | `-m <节点组>` | 如 `GPUgroup_X86_e0n6530_1T_4090` |
| 卡数 + CPU 核数 | `-gpgpu <卡数>` `-n <核数>` | 按需填写，见每卡"可选项"表 |

**一条通用命令模板**（所有卡都能套）：
```bash
jsub -n <CPU核数> -gpgpu <GPU卡数> -q <队列> -m <节点组> -J <作业名> -o output.%J -e error.%J "<你的命令>"
```

**切换示例**：把 4090 换成 A800 —— 只改两处 `-q gpu_4090 → -q gpu_a800`、`-m ..._4090 → -m ..._A800`，核数按需调整即可。

---

## 1. 全景速查表（显卡 → 切换命令）

> `-n 8 -gpgpu 1` 是最常用默认值，可按下面的"可选项"改成任意核数。

| 显卡 | 节点组 | 队列 | 切换命令 |
|---|---|---|---|
| **RTX 4090** | `GPUgroup_X86_e0n6530_1T_4090` | `gpu_4090` | `jsub -n 8 -gpgpu 1 -q gpu_4090 -m GPUgroup_X86_e0n6530_1T_4090 -J job -o output.%J -e error.%J "python3 train.py"` |
| **RTX 6000 Ada** | `GPUgroup_X86_e0n6530_1T_6000ada` | `gpu_6000ada` | `jsub -n 8 -gpgpu 1 -q gpu_6000ada -m GPUgroup_X86_e0n6530_1T_6000ada -J job -o output.%J -e error.%J "python3 train.py"` |
| **H100** | `GPUgroup_X86_xeon6530_1T_H100` | `gpu_h100` | `jsub -n 8 -gpgpu 1 -q gpu_h100 -m GPUgroup_X86_xeon6530_1T_H100 -J job -o output.%J -e error.%J "python3 train.py"` |
| **A800** | `GPUgroup_X86_e0n8358P_1T_A800` | `gpu_a800` | `jsub -n 8 -gpgpu 1 -q gpu_a800 -m GPUgroup_X86_e0n8358P_1T_A800 -J job -o output.%J -e error.%J "python3 train.py"` |
| **昇腾 910A** | `GPUgroup_X86_e0n8558p_1T_910A` | ※待确认 | `jsub -n 8 -gpgpu 1 -q <队列> -m GPUgroup_X86_e0n8558p_1T_910A -J job -o output.%J -e error.%J "python3 train.py"` |
| **H200** | `GPUgroup_X86_e0n8558p_2T_h200` | ※待确认 | `jsub -n 8 -gpgpu 1 -q <队列> -m GPUgroup_X86_e0n8558p_2T_h200 -J job -o output.%J -e error.%J "python3 train.py"` |
| **RTX PRO 6000** | `GPUgroup_X86_e0n8558p_2T_PR06000` | ※待确认 | `jsub -n 8 -gpgpu 1 -q <队列> -m GPUgroup_X86_e0n8558p_2T_PR06000 -J job -o output.%J -e error.%J "python3 train.py"` |
| **昇腾 910C** | `npu_910C` | ※待确认 | `jsub -n 8 -gpgpu 1 -q <队列> -m npu_910C -J job -o output.%J -e error.%J "python3 train.py"` |

> ※ 手册"常用队列"只列了 `gpu_4090 / gpu_a800 / gpu_h800 / gpu_6000ada` 和 CPU 队列。H200、910A/910C、PRO6000 对应队列名未在手册给出，提交前先跑：
> ```bash
> jqueues -u "$USER"      # 看自己有哪些队列可用
> jhostgroup              # 看全部节点组
> ```
> 把 `<队列>` 换成实际队列名即可，其余参数完全一样。

---

## 2. 单卡详解

### 2.1 RTX 4090（CUDA · NVIDIA）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n6530_1T_4090` |
| 队列 | `gpu_4090` |
| 显存 | 24 GB |
| 软件栈 | cuda / pytorch（`module avail` 查看版本，或用自己的容器） |

**命令行提交**：
```bash
jsub -n 8 -gpgpu 1 -q gpu_4090 -m GPUgroup_X86_e0n6530_1T_4090 \
     -J 4090_job -o output.%J -e error.%J "python3 train.py"
```

**脚本提交**（`submit_4090.sh`）：
```bash
#!/bin/bash
#JSUB -q gpu_4090
#JSUB -m GPUgroup_X86_e0n6530_1T_4090
#JSUB -gpgpu 1
#JSUB -n 8
#JSUB -o output.%J
#JSUB -e error.%J
#JSUB -W 48:00
#JSUB -J 4090_job

module purge
module load cuda/12.6.3      # 版本以 module avail 为准
module load python/pytorch-2.5.1  # 版本以 module avail 为准
python3 train.py
```
提交：`jsub < submit_4090.sh`

**可选项（CPU/GPU 核数随便选）**：

| 参数 | 含义 | 可选值 | 建议 |
|---|---|---|---|
| `-n` | CPU 核数 | 1 ~ 节点核数上限（`jhosts -l gpu01` 查） | 8 |
| `-gpgpu` | GPU 卡数 | 1 ~ 8（视节点配置，通常单节点 8 卡） | 1 |
| `-W` | 时限（分钟） | `24:00` ~ `168:00` | `48:00` |

**验证**：`jjobs` 看状态；作业内 `nvidia-smi` 确认拿到的是 4090。

---

### 2.2 RTX 6000 Ada（CUDA · NVIDIA）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n6530_1T_6000ada` |
| 队列 | `gpu_6000ada` |
| 显存 | 48 GB |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q gpu_6000ada -m GPUgroup_X86_e0n6530_1T_6000ada \
     -J ada_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_6000ada.sh`）：
```bash
#!/bin/bash
#JSUB -q gpu_6000ada
#JSUB -m GPUgroup_X86_e0n6530_1T_6000ada
#JSUB -gpgpu 1
#JSUB -n 8
#JSUB -o output.%J
#JSUB -e error.%J
#JSUB -W 48:00
#JSUB -J ada_job

module purge
module load cuda/12.6
module load pytorch/2.5.1
python3 train.py
```

**可选项**：同 2.1（`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需）。

---

### 2.3 H100（CUDA · NVIDIA）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_xeon6530_1T_H100` |
| 队列 | `gpu_h100`（用户实测确认） |
| 显存 | 80 GB |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q gpu_h100 -m GPUgroup_X86_xeon6530_1T_H100 \
     -J h100_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_h100.sh`）：把 2.1 的脚本改 `-q gpu_h100`、`-m GPUgroup_X86_xeon6530_1T_H100` 即可。

**可选项**：`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需。

---

### 2.4 A800（CUDA · NVIDIA）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n8358P_1T_A800` |
| 队列 | `gpu_a800` |
| 显存 | 80 GB |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q gpu_a800 -m GPUgroup_X86_e0n8358P_1T_A800 \
     -J a800_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_a800.sh`）：同 2.1，改 `-q gpu_a800`、`-m GPUgroup_X86_e0n8358P_1T_A800`。

**可选项**：`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需。

---

### 2.5 昇腾 910A（NPU · 华为 Ascend）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n8558p_1T_910A` |
| 队列 | ※待确认（`jqueues -u "$USER"` 查看；常见命名如 `npu_910a` 等，以实际为准） |
| 显存 | 以 `npu-smi info` 为准 |
| 软件栈 | CANN + torch_npu（昇腾专用，**不是 CUDA**） |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q <队列> -m GPUgroup_X86_e0n8558p_1T_910A \
     -J ascend_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_910a.sh`）：
```bash
#!/bin/bash
#JSUB -q <队列>                      # 改成 jqueues 确认的队列
#JSUB -m GPUgroup_X86_e0n8558p_1T_910A
#JSUB -gpgpu 1
#JSUB -n 8
#JSUB -o output.%J
#JSUB -e error.%J
#JSUB -W 48:00
#JSUB -J ascend_job

module purge
module load ascend-toolkit        # CANN 环境，以 module avail 为准
module load torch_npu             # 以 module avail 为准
python3 train.py
```

**可选项**：`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需。
**验证**：作业内 `npu-smi info`（昇腾用 npu-smi，不是 nvidia-smi）。

---

### 2.6 H200（CUDA · NVIDIA）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n8558p_2T_h200` |
| 队列 | ※待确认（按命名规律可能为 `gpu_h200`，以 `jqueues` 为准） |
| 显存 | 141 GB（大显存跑大模型首选） |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q gpu_h200 -m GPUgroup_X86_e0n8558p_2T_h200 \
     -J h200_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_h200.sh`）：同 2.1，改 `-q gpu_h200`、`-m GPUgroup_X86_e0n8558p_2T_h200`。

**可选项**：`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需。

---

### 2.7 RTX PRO 6000（CUDA · NVIDIA，Blackwell）

| 项 | 值 |
|---|---|
| 节点组 | `GPUgroup_X86_e0n8558p_2T_PR06000` |
| 队列 | ※待确认（截图 OCR 显示 `PR06000`，判读为 RTX PRO 6000；以 `jhosts` / `nvidia-smi` 为准） |
| 显存 | 96 GB |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q <队列> -m GPUgroup_X86_e0n8558p_2T_PR06000 \
     -J pro6000_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**（`submit_pro6000.sh`）：同 2.1，改 `-q <队列>`、`-m GPUgroup_X86_e0n8558p_2T_PR06000`，cuda 建议 12.8+。

**可选项**：`-n` 1~节点上限；`-gpgpu` 1~8；`-W` 按需。

---

### 2.8 昇腾 910C（NPU · 华为 Ascend）

| 项 | 值 |
|---|---|
| 节点组 | `npu_910C` |
| 队列 | ※待确认（`jqueues -u "$USER"` 查看，可能为 npu 专用队列） |
| 软件栈 | CANN + torch_npu（昇腾专用） |

**命令行**：
```bash
jsub -n 8 -gpgpu 1 -q <队列> -m npu_910C \
     -J 910c_job -o output.%J -e error.%J "python3 train.py"
```

**脚本**：同 2.5，改 `-m npu_910C`、队列名。
**验证**：作业内 `npu-smi info`。

---

## 3. CPU 节点组（纯 CPU 作业，不需要显卡）

截图里还有 7 个 CPU 节点组，一并整理（队列参考手册，需 `jqueues` 确认）：

| 节点组 | CPU | 内存 | 对应队列（参考） |
|---|---|---|---|
| `CPUgroup_ARM_kunpeng920_1T` | 鲲鹏 920（ARM） | 1T | `cpu_arm1` / `cpu_arm2` |
| `CPUgroup_ARM_kunpeng920_512G` | 鲲鹏 920（ARM） | 512G | `cpu_arm1` / `cpu_arm2` |
| `CPUgroup_ARM_kunpeng920_512G_openEuler` | 鲲鹏 920（ARM，openEuler 系统） | 512G | `cpu_arm2` / `cpu_armfat1` |
| `CPUgroup_X86_e0n8358P_256G` | x86 | 256G | `cpu_x86` / `cpu_x86thin` |
| `CPUgroup_X86_e0n8358P_512G` | x86 | 512G | `cpu_x86` |
| `CPUgroup_X86_e0n8378C_512G` | x86 | 512G | `cpu_x86` |
| `CPUgroup_X86_e0n8538P_1T` | x86 | 1T | `cpu_x86fat` |

**CPU 作业命令模板**（不写 `-gpgpu` 就是纯 CPU）：
```bash
jsub -n 16 -q cpu_x86 -m CPUgroup_X86_e0n8358P_512G -J cpu_job -o output.%J -e error.%J "python3 calc.py"
```
ARM 节点同理，换队列和节点组即可。`-n` 核数按需填写（1~节点上限）。

> 截图里还有 `groupl`、`mgrouplfi` 两个节点组，疑似平台内部/测试组，正常作业不要提交到它们。

---

## 4. 切换显卡 · 手把手流程

1. **查权限**：`jqueues -u "$USER"` —— 看自己能用的队列（没权限会排队或失败）。
2. **查节点组**：`jhostgroup` —— 确认节点组名（和本手册对上号）。
3. **查核数上限**：`jhosts -l <节点名>` 或 `jhosts attrib -l <节点名>` —— 看该组 CPU 总核数、内存、GPU 数。
4. **查配额**：`jlimits -n` —— 配额满也会排队。
5. **提交**：按第 1/2 节模板填 `-n`、`-gpgpu`、`-q`、`-m`，提交。
6. **换卡**：改 `-q` + `-m`（+ 核数），重新提交即可。想更省事，直接跑配套脚本 `bash gpu_switch.sh`。

---

## 5. 常用配套命令（切换时随手要用）

```bash
jqueues -u "$USER"      # 可用队列
jhostgroup              # 节点组列表
jhosts                  # 节点状态
jhosts -l gpu01         # 节点详情（核数、GPU、NUMA）
jhosts attrib -l gpu01  # 静态硬件资源
jlimits -n              # 用户配额
jjobs                   # 当前作业
jjobs -l <作业ID>       # 作业详情
jctrl kill <作业ID>     # 取消作业
jhist                   # 历史作业
jmod -W 60 -n 4 <作业ID> # 改已提交作业的核数/时限
nvidia-smi              # 作业内确认 NVIDIA 卡
npu-smi info            # 作业内确认昇腾卡
module avail            # 可加载的软件环境
```

---

## 6. 常见坑（切换时最容易踩的）

| 坑 | 说明 |
|---|---|
| ❌ 队列名写错 | 手册队列列表不全，**提交前必须 `jqueues -u $USER` 确认**；没有 `default` 队列 |
| ❌ Windows 写的脚本 | 必须先 `dos2unix submit.sh`，否则可能提交失败 |
| ❌ 忘记 `module purge` | 多版本 cuda 冲突；`module load` 前先 `purge` |
| ❌ MPI 没指定节点类型 | `-R "select[type==LINUX64] ..."`，否则可能派到 view 节点导致 MPI 失败 |
| ❌ 昇腾卡当 CUDA 用 | 昇腾必须用 CANN + torch_npu，代码要 `torch.npu` 适配；不是 nvidia-smi |
| ❌ 核数超过节点上限 | 排队甚至失败，`jhosts` 先查该组总核数 |
| ❌ 资源空闲却排队 | 大概率配额满了：`jlimits -n` 确认 |
| ❌ `-gpgpu` 不写 | GPU 队列作业没申请到卡，白跑 CPU |

---

*整理依据：官方《西电高性能计算（专用超算）中心使用指南》＋ 平台"集群状态"节点组截图。节点组/队列名如有出入，以平台实际输出为准。*
