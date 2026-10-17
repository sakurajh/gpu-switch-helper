#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
西电超算 · GPU 切换助手  (Windows exe)

功能：选择节点组 -> 选择节点 -> 选择 CPU/GPU 核数（超上限禁止）-> 选择运行时限（可不限）
      -> 填写运行命令 / 脚本（支持多行 shell / python）
      -> 生成"一整个"提交脚本（#JSUB 头 + 运行内容）+ 单行 jsub 指令
队列按显卡自动锁定；保存脚本时由用户选择保存路径。

用法：
  GPU切换助手.exe                打开图形界面
  GPU切换助手.exe --selftest     自测（无界面，结果写 gpu_switch_selftest.txt）
  GPU切换助手.exe --smoke        冒烟（界面打开 2 秒后自动关闭）

界面（v1.21 起）：左侧选节点组/节点、核数、时限、环境模块；
右侧上方写运行内容，下方看生成结果，按钮就近放在各自面板里。
上次填写的内容会在关闭时记住（存在用户目录 ~/.gpu_switch_helper.json），
点「重置」可清掉。资源图标一律按运行时相对路径查找，不写死盘符。
"""
import base64
import json
import os
import sys
import time
import traceback

# ============================================================================
# 界面主题配色（浅色现代风：灰底 + 白色卡片 + 蓝色强调）
# ============================================================================
BG = "#eef2f8"
BANNER = "#3b6fe0"
CARD = "#ffffff"
CARD2 = "#e3eaf6"
CARD_HEAD = "#f5f8fd"     # 卡片标题条
LINE = "#dbe3f0"          # 卡片描边
STATUS_BG = "#e3eaf6"     # 底部状态栏
FG = "#223043"
FG2 = "#64748b"
FG3 = "#8a97ab"
ACCENT = "#3b6fe0"
ACCENT_HI = "#5b85ee"
ACCENT_DARK = "#2f57b8"
INFO = "#0b7ecb"
WARN = "#d64545"
CODE_BG = "#101a2b"
CODE_FG = "#d9e2f3"

# 字号按『高分屏 150% 缩放』调校过：Tk 的 point 会随系统 DPI 放大，
# 用 12pt 会让整个界面撑到一屏放不下，所以正文用 10pt、标题用 14pt。
FONT = ("Microsoft YaHei UI", 10)
FONT_H = ("Microsoft YaHei UI", 11, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_CODE = ("Consolas", 10)
FONT_CARD = ("Microsoft YaHei UI", 10, "bold")

# 程序版本（显示在窗口标题与横幅，方便确认是否为最新）
VERSION = "1.22"

# 运行时限可选项（"不限制" = 不加 -W 参数）
TIME_OPTIONS = ["不限制", "12:00", "24:00", "48:00", "72:00", "120:00", "168:00"]

# 运行内容类型（决定生成格式：Python 代码自动用 heredoc 包好，指令/Shell 原样执行）
CONTENT_KINDS = ["自动识别", "指令 / Shell", "Python 代码"]

# 默认推荐环境（平台 module avail 已验证的可用模块）
ENV_DEFAULT = ["python/pytorch-2.5.1"]
ENV_MODULES = [
    ("CUDA（显卡计算）", ["cuda/11.8.0", "cuda/12.2.0", "cuda/12.4.0", "cuda/12.6.3", "cuda/12.8.1", "cuda/13.0.0", "cuda/13.2.1"]),
    ("Python / 机器学习", ["python/anaconda-2023.03", "python/pytorch-2.5.1", "python/tf2.6.2", "python/deepmd-3.0", "python/esmfold2-3.4.1", "python/foldseek-10.941cd33", "python/proteinmpnn-0.1.3"]),
    ("MPI 并行", ["openmpi/4.1.1-gcc-11.3.1", "openmpi/4.1.7-gcc-11.3.1", "mpich/4.3.0b1-gcc-11.3.1", "intel/mpi-2021.6.0", "intel/mpi-2021.14"]),
    ("科学计算软件", ["gromacs/2026.0-cuda12.8.1-gcc-11.3.1", "gromacs/2024.1-gcc-11.3.1", "lammps/20230802.3-gcc-11.3.1", "namd/3.0.1-multicore-CUDA", "vasp/6.4.3-oneapi-mpi-2021.6.0", "wrf/4.7.1-gcc-11.3.1"]),
    ("数学库 / 其它", ["cudnn/9.6.074_cuda12", "nccl/2.28.9-1-cuda13.0", "openblas/0.3.26-gcc-11.3.1", "fftw/3.3.10-gcc-11.3.1", "cmake/3.27.9-gcc-11.3.1", "vtk/9.2.6-gcc-11.3.1"]),
]


# ============================================================================
# 平台资源清单：每组 {group 节点组, queue 队列(按显卡锁定), queue_confirmed 是否经确认,
#                  kind CPU/GPU/NPU, nodes [(节点名, CPU核数, GPU卡数)]}
# ============================================================================
RESOURCES = [
    # ---------- CPU 节点组（无 GPU） ----------
    {"group": "CPUgroup_ARM_kunpeng920_1T", "queue": "cpu_armfat1", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("armfat01", 128, 0), ("armfat02", 128, 0), ("armfat03", 128, 0), ("armfat04", 128, 0)]},
    {"group": "CPUgroup_ARM_kunpeng920_512G", "queue": "cpu_arm1", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("arm01", 128, 0), ("arm02", 128, 0), ("arm03", 128, 0), ("arm04", 128, 0), ("arm05", 128, 0),
               ("arm06", 128, 0), ("arm07", 128, 0), ("arm08", 128, 0), ("arm09", 128, 0), ("arm10", 128, 0),
               ("arm11", 128, 0)]},
    {"group": "CPUgroup_ARM_kunpeng920_512G_openEuler", "queue": "cpu_arm2", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("arm12", 128, 0), ("arm13", 128, 0), ("arm14", 128, 0), ("arm15", 128, 0), ("arm16", 128, 0),
               ("arm17", 128, 0)]},
    {"group": "CPUgroup_X86_xeon8358P_256G", "queue": "cpu_x86thin", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("cu08", 64, 0), ("cu09", 64, 0), ("cu10", 64, 0), ("cu11", 64, 0), ("cu12", 64, 0), ("cu13", 64, 0)]},
    {"group": "CPUgroup_X86_xeon8358P_512G", "queue": "cpu_x86thin", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("cu06", 64, 0), ("cu07", 64, 0)]},
    {"group": "CPUgroup_X86_xeon8378C_512G", "queue": "cpu_x86", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("cu01", 76, 0), ("cu02", 76, 0), ("cu03", 76, 0), ("cu04", 76, 0), ("cu05", 76, 0)]},
    {"group": "CPUgroup_X86_xeon8538P_1T", "queue": "cpu_x86fat", "queue_confirmed": True, "kind": "CPU",
     "nodes": [("fat01", 64, 0), ("fat02", 64, 0), ("fat03", 64, 0), ("fat04", 64, 0), ("fat05", 64, 0),
               ("fat06", 64, 0)]},
    # ---------- GPU / NPU 节点组（队列按显卡锁定） ----------
    {"group": "GPUgroup_X86_xeon6530_1T_4090", "queue": "gpu_4090", "queue_confirmed": True, "kind": "GPU",
     "nodes": [("gpu02", 64, 8), ("gpu03", 64, 8), ("gpu04", 64, 8), ("gpu05", 64, 8), ("gpu06", 64, 8),
               ("gpu07", 64, 8), ("gpu08", 64, 8), ("gpu09", 64, 8), ("gpu10", 64, 8)]},
    {"group": "GPUgroup_X86_Xeon6530_1T_6000ada", "queue": "gpu_6000ada", "queue_confirmed": True, "kind": "GPU",
     "nodes": [("gpu13", 64, 8), ("gpu14", 64, 8), ("gpu15", 64, 8), ("gpu16", 64, 8), ("gpu17", 64, 8),
               ("gpu18", 64, 8), ("gpu19", 64, 8), ("gpu20", 64, 8), ("gpu21", 64, 8), ("gpu22", 64, 8),
               ("gpu25", 64, 8)]},
    {"group": "GPUgroup_X86_xeon6530_1T_H100", "queue": "gpu_h100", "queue_confirmed": True, "kind": "GPU",
     "nodes": [("gpu01", 64, 4)]},
    {"group": "GPUgroup_X86_Xeon8358P_1T_A800", "queue": "gpu_a800", "queue_confirmed": True, "kind": "GPU",
     "nodes": [("gpu23", 64, 2), ("gpu24", 64, 2)]},
    {"group": "GPUgroup_X86_Xeon8558p_1511G_K100AI", "queue": "gpu_k100ai", "queue_confirmed": True, "kind": "GPU",
     "nodes": [("gpu26", 96, 8)]},
    {"group": "GPUgroup_X86_Xeon8558p_2T_h200", "queue": "gpu_h200", "queue_confirmed": False, "kind": "GPU",
     "nodes": [("gpu27", 96, 4)]},
    {"group": "GPUgroup_X86_Xeon8558p_2T_PRO6000", "queue": "gpu_pro6000", "queue_confirmed": False, "kind": "GPU",
     "nodes": [("gpu28", 96, 8)]},
    {"group": "npu_910c节点组", "queue": "npu_910c", "queue_confirmed": False, "kind": "NPU",
     "nodes": [("gpu29", 320, 16)]},
]

QUEUE_NOTE = "队列名已按平台 jqueues 实测核对（CPU 组：cpu_x86 / cpu_x86thin / cpu_x86fat / cpu_arm1 / cpu_arm2 / cpu_armfat1）。H200、PRO6000 队列平台确有但可能未对你的账号开通；NPU 组平台暂无队列。提交前仍建议 jqueues -u $USER 核对。"

# ============================================================================
# 示例运行内容（快捷自检：约 30 秒跑完，CPU / GPU 都能直接运行）
# ============================================================================
EXAMPLE_TEXT = r"""# ===== 快捷自检（约 30 秒跑完；CPU 节点、GPU 节点都能直接运行）=====
echo "===== 自检开始 ====="
echo "主机: $(hostname)"
echo "CPU 核数: $(nproc)"
date

# 有 nvidia-smi 就打印显卡信息（没有就跳过）
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi
else
    echo "（本节点没有 nvidia-smi，显卡型号请看下方 torch 输出）"
fi

# 用「环境配置」里选的 python 做个小验证（不选也能跑）
python3 - << 'PYEOF'
import sys
print("Python 版本:", sys.version.split()[0])
print("小测试 2+2 =", 2 + 2)
try:
    import torch
    print("torch", torch.__version__, "| CUDA 可用:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("显卡型号:", torch.cuda.get_device_name(0))
except ImportError:
    print("（当前环境没有 torch —— 需要 GPU 计算请在『环境配置』勾选 python/pytorch-2.5.1）")
PYEOF

echo "===== 自检结束 ====="

"""


# ============================================================================
# 内置使用手册内容（样式跟随应用主题，应用内直接展示）
# ============================================================================
MANUAL_SECTIONS = [
    ("h1", "一、快速上手"),
    ("body", "三步生成作业指令：\n① 选节点组 → 选节点；\n② 填 CPU/GPU 核数、作业名、运行时限（可不限）；\n③ 在「运行命令/脚本」框写命令或脚本 → 生成 → 复制或保存。\n队列已按显卡自动锁定；保存脚本时可自选保存路径。"),
    ("h1", "二、平台登录"),
    ("h2", "门户（网页）"),
    ("body", "浏览器打开 https://xqhpc.xidian.edu.cn，统一身份认证登录进入 HPC 应用门户。首次登录需平台审核通过。"),
    ("h2", "SSH 登录"),
    ("body", "登录门户后，在「应用仓库」获取 SSH 密钥，用 Xshell 等工具连接登录节点；也可直接打开门户的 terminal 应用。"),
    ("h1", "三、显卡切换速查"),
    ("table", [["显卡", "队列", "显存"],
               ["RTX 4090", "gpu_4090", "24 GB"],
               ["RTX 6000 Ada", "gpu_6000ada", "48 GB"],
               ["H100", "gpu_h100", "80 GB"],
               ["A800", "gpu_a800", "80 GB"],
               ["H200", "gpu_h200(需申请权限)", "141 GB"],
               ["RTX PRO 6000", "gpu_pro6000(需申请权限)", "96 GB"],
               ["昇腾 910C", "平台暂无 NPU 队列", "-"]]),
    ("note", "标注“需申请权限”的队列平台确有，但个人账号可能未开通；提交前用 jqueues -u $USER 核对。"),
    ("body", "CPU 队列（已核对）：cu01-cu05 → cpu_x86；cu06-cu13 → cpu_x86thin；fat01-fat06 → cpu_x86fat；"
             "arm01-arm11 → cpu_arm1；arm12-arm17 → cpu_arm2；armfat01-armfat04 → cpu_armfat1。"),
    ("h1", "四、调度命令速查"),
    ("table", [["命令", "功能"],
               ["jsub < submit.sh", "提交作业"],
               ["jjobs", "查看当前作业"],
               ["jctrl kill 作业号", "取消作业"],
               ["jqueues -u $USER", "查看可用队列"],
               ["jhostgroup", "查看节点组"],
               ["jhosts -l 节点名", "节点详情（核数/GPU）"],
               ["jlimits -n", "查看配额"],
               ["jhist", "历史作业"],
               ["jmod -W 60 -n 4 作业号", "修改作业参数"]]),
    ("h1", "五、提交脚本模板"),
    ("code", "#!/bin/bash\n#JSUB -q gpu_h100\n#JSUB -m gpu01\n#JSUB -gpgpu 4\n#JSUB -n 64\n#JSUB -o output.%J\n#JSUB -e error.%J\n#JSUB -W 48:00\n#JSUB -J my_job\n\nmodule purge\nmodule load cuda/12.6.3\npython3 train.py"),
    ("body", "提交方式：jsub < submit.sh（Windows 上传前先 dos2unix）"),
    ("h1", "六、软件环境 module"),
    ("body", "module avail 查看全部可用环境；加载前先 module purge，避免版本冲突。"),
    ("code", "module purge\nmodule load cuda/12.6.3\nmodule load python/pytorch-2.5.1"),
    ("h1", "七、常见问题"),
    ("body", "· 一直排队：资源不足或配额已满，用 jlimits -n 查看。\n· 脚本提交失败：Windows 编辑的脚本先 dos2unix。\n· 缺库文件：加载正确版本的软件环境，检查 LD_LIBRARY_PATH。\n· 昇腾卡：用 CANN + torch_npu（npu-smi info），不是 CUDA。\n· 日志：-o 为标准输出，-e 为错误输出。"),
    ("h1", "八、联系方式"),
    ("body", "用户交流 QQ 群：81892673；联系电话以门户页面公布为准。"),
]


# ============================================================================
# 校验与指令生成（核心逻辑）
# ============================================================================
def find_group(gname):
    for g in RESOURCES:
        if g["group"] == gname:
            return g
    return None


def find_node(group, nname):
    for n in group["nodes"]:
        if n[0] == nname:
            return n
    return None


def safe_int(value, default=0):
    """把界面上任意输入安全转成整数；转不了就返回 default。
    防止在核数框里误输入字母后切换节点时 int() 抛异常（打包成无控制台 exe 时会静默卡死）。"""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    s = str(value).strip()
    try:
        return int(s)
    except (TypeError, ValueError):
        pass
    # 末尾混进了非数字（例如手滑打成 "8bc"）时，保留前面已经打对的数字，
    # 不要把用户输入整个抹掉；完全没数字（或像小数）才回落到 default。
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if i and s[i:i + 1] != ".":
        return int(s[:i])
    return default


def valid_cpu(group, node, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return False
    return 1 <= n <= node[1]


def valid_gpu(group, node, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return False
    return node[2] > 0 and 1 <= n <= node[2]


def _timelimit_line(timelimit):
    """返回 -W 相关参数；timelimit 为空或"不限制"则不加（一直运行）。"""
    if timelimit and timelimit != "不限制":
        return timelimit
    return None


def looks_like_python(content):
    """粗判运行内容是否像是直接贴进去的 Python 代码（会被 bash 当命令执行而报错）。"""
    for line in (content or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("#!/usr/bin/env python") or s.startswith("#!/usr/bin/python"):
            return True
        return s.startswith(("import ", "from ", "def ", "class ", "if __name__", "print("))
    return False


def resolve_content_kind(kind_choice, content):
    """根据用户选择的类型 + 内容自动判定：返回 'python' 或 'shell'。"""
    if kind_choice == "Python 代码":
        return "python"
    if kind_choice == "指令 / Shell":
        return "shell"
    return "python" if looks_like_python(content) else "shell"


def build_command(group, node, cpu, gpu, jobname, runcmd, timelimit=None):
    """生成单行 jsub 指令。CPU 组不写 -gpgpu；GPU/NPU 组才写。队列由显卡锁定。"""
    parts = ["jsub"]
    parts.append("-n %d" % int(cpu))
    if node[2] > 0 and int(gpu) > 0:
        parts.append("-gpgpu %d" % int(gpu))
    parts.append("-q %s" % group["queue"])
    parts.append("-m %s" % node[0])
    parts.append("-J %s" % (jobname.strip() or "my_job"))
    tl = _timelimit_line(timelimit)
    if tl:
        parts.append("-W %s" % tl)
    parts.append("-o output.%J")
    parts.append("-e error.%J")
    runcmd = runcmd.strip() or "python3 train.py"
    parts.append('"%s"' % runcmd)
    return " ".join(parts)


def env_bootstrap_block(env_list):
    """环境配置段：根据所选模块生成 module purge + module load 行。"""
    lines = ["# ===== 环境配置（软件自动生成；可整段删除后自行管理环境）====="]
    mods = [m for m in (env_list or []) if m]
    if mods:
        lines.append("module purge")
        for m in mods:
            lines.append("module load %s" % m)
    else:
        lines.append("# 未选择环境模块（不加载 module，环境请自行处理）")
    return "\n".join(lines)


def build_script(group, node, cpu, gpu, jobname, runcontent, timelimit=None, env_list=None, content_kind="shell"):
    """生成完整提交脚本：#JSUB 头（队列按显卡锁定）+ 环境配置 + 运行内容。
    content_kind: 'shell' 原样执行；'python' 自动用 heredoc 包好交给 python3 运行。"""
    queue = group["queue"]
    lines = ["#!/bin/bash"]
    lines.append("# 由「GPU切换助手 v%s」生成 —— 提交：上传集群后 dos2unix submit_%s.sh && jsub < submit_%s.sh" % (VERSION, node[0], node[0]))
    lines.append("#JSUB -q %s" % queue)
    lines.append("#JSUB -m %s" % node[0])
    if node[2] > 0 and int(gpu) > 0:
        lines.append("#JSUB -gpgpu %d" % int(gpu))
    lines.append("#JSUB -n %d" % int(cpu))
    if group["kind"] in ("GPU", "NPU"):
        lines.append('#JSUB -R "select[type==LINUX64]"')
    lines.append("#JSUB -o output.%J")
    lines.append("#JSUB -e error.%J")
    tl = _timelimit_line(timelimit)
    if tl:
        lines.append("#JSUB -W %s" % tl)
    lines.append("#JSUB -J %s" % (jobname.strip() or "my_job"))
    lines.append("")
    lines.append('cd "${JH_SUB_CWD:-.}" 2>/dev/null || true')
    lines.append("")
    lines.append(env_bootstrap_block(env_list))
    lines.append("")
    content = runcontent.strip("\n")
    if not content:
        content = "python3 train.py"
        content_kind = "shell"
    if content_kind == "python":
        py_file = "run_%s.py" % node[0]
        py_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        lines.append('echo "%s" | base64 -d > %s' % (py_b64, py_file))
        lines.append("python3 %s" % py_file)
    else:
        lines.append(content)
    return "\n".join(lines) + "\n"


def build_submit_block(group, node, cpu, gpu, jobname, runcontent, timelimit=None, env_list=None, content_kind="shell"):
    """生成『复制到集群粘贴即提交』整段：整个脚本转成一行 base64，粘贴不会丢字/错位。
    base64 全 ASCII、无换行，规避终端粘贴中文注释或多行 heredoc 被截断的问题。"""
    script = build_script(group, node, cpu, gpu, jobname, runcontent, timelimit, env_list, content_kind)
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    fname = "submit_%s.sh" % node[0]
    lines = [
        "# ===== 直接提交版：复制下面整段到集群粘贴回车（整脚本已编码为一行 base64，粘贴不会错位）===== #",
        'echo "%s" | base64 -d > %s' % (b64, fname),
        # base64 解码出的换行已是干净 \n，无需 dos2unix；仅当集群装了才执行，避免 command not found
        "command -v dos2unix >/dev/null 2>&1 && dos2unix %s" % fname,
        "jsub < %s" % fname,
        "",
    ]
    return "\n".join(lines)


def run_content_is_single_line(runcontent):
    content = runcontent.strip("\n").strip()
    return bool(content) and "\n" not in content


# ============================================================================
# 自测
# ============================================================================
def selftest():
    report = []
    ok = True

    def bad(msg):
        nonlocal ok
        ok = False
        report.append("  [FAIL] " + msg)

    total_nodes = 0
    for g in RESOURCES:
        gname = g["group"]
        for node in g["nodes"]:
            total_nodes += 1
            nname, cpus, gpus = node
            for v in (1, cpus):
                if not valid_cpu(g, node, v):
                    bad("%s/%s CPU=%d 应合法" % (gname, nname, v))
            for v in (0, cpus + 1, -1, "abc"):
                if valid_cpu(g, node, v):
                    bad("%s/%s CPU=%r 应非法" % (gname, nname, v))
            if gpus > 0:
                for v in (1, gpus):
                    if not valid_gpu(g, node, v):
                        bad("%s/%s GPU=%d 应合法" % (gname, nname, v))
                for v in (0, gpus + 1, -1, "x"):
                    if valid_gpu(g, node, v):
                        bad("%s/%s GPU=%r 应非法" % (gname, nname, v))
            else:
                if valid_gpu(g, node, 1):
                    bad("%s/%s 无GPU节点 GPU=1 应非法" % (gname, nname))

            cmd = build_command(g, node, cpus, gpus, "selftest", "python3 t.py", "48:00")
            for token in ("-n %d" % cpus, "-q %s" % g["queue"], "-m %s" % nname, "-J selftest", "-W 48:00"):
                if token not in cmd:
                    bad("%s/%s 指令缺 %s" % (gname, nname, token))
            if gpus > 0:
                if "-gpgpu %d" % gpus not in cmd:
                    bad("%s/%s 指令缺 -gpgpu" % (gname, nname))
            else:
                if "-gpgpu" in cmd:
                    bad("%s/%s 无GPU节点不应出现 -gpgpu" % (gname, nname))
            cmd_u = build_command(g, node, cpus, gpus, "selftest", "python3 t.py", "不限制")
            if "-W" in cmd_u:
                bad("%s/%s 不限制时限时指令不应出现 -W" % (gname, nname))

            runbody = "module purge\nmpirun -np 8 ./app.x\n"
            script = build_script(g, node, cpus, gpus, "selftest", runbody, "48:00")
            for token in ("#JSUB -q %s" % g["queue"], "#JSUB -m %s" % nname, "#JSUB -n %d" % cpus,
                          "#JSUB -W 48:00", "#JSUB -J selftest", "mpirun -np 8 ./app.x"):
                if token not in script:
                    bad("%s/%s 脚本缺 %s" % (gname, nname, token))
            script_u = build_script(g, node, cpus, gpus, "selftest", runbody, "不限制")
            if "#JSUB -W" in script_u:
                bad("%s/%s 不限制时限时脚本不应含 -W" % (gname, nname))
            script_env = build_script(g, node, cpus, gpus, "selftest", runbody, "48:00", ["python/pytorch-2.5.1", "cuda/12.4.0"])
            if "环境配置" not in script_env or "module purge" not in script_env \
                    or "module load python/pytorch-2.5.1" not in script_env or "module load cuda/12.4.0" not in script_env:
                bad("%s/%s 环境配置段异常" % (gname, nname))
            script_noenv = build_script(g, node, cpus, gpus, "selftest", runbody, "48:00", [])
            if "module load" in script_noenv:
                bad("%s/%s 未选环境时脚本不应出现 module load" % (gname, nname))
            py_script = build_script(g, node, cpus, gpus, "selftest", "import torch\nprint(torch.__version__)\n",
                                     "48:00", ["python/pytorch-2.5.1"], "python")
            if ("base64 -d > run_%s.py" % nname) not in py_script or ("python3 run_%s.py" % nname) not in py_script:
                bad("%s/%s Python 代码未按 base64 写文件运行" % (gname, nname))
            try:
                _pb = py_script.split('echo "')[1].split('" | base64 -d')[0]
                _pd = base64.b64decode(_pb).decode("utf-8").rstrip("\n")
                if _pd != "import torch\nprint(torch.__version__)":
                    bad("%s/%s Python base64 解码不一致" % (gname, nname))
            except Exception:
                bad("%s/%s Python base64 解码异常" % (gname, nname))
            sh_script = build_script(g, node, cpus, gpus, "selftest", "echo hi\n", "48:00", [], "shell")
            if "<< 'PYEOF'" in sh_script or "base64 -d > run_" in sh_script:
                bad("%s/%s Shell 指令不应被包裹" % (gname, nname))
            if resolve_content_kind("自动识别", "import torch\nx=1\n") != "python" \
                    or resolve_content_kind("自动识别", "echo hi\n") != "shell":
                bad("自动识别逻辑异常")
            block = build_submit_block(g, node, cpus, gpus, "selftest", runbody, "48:00", ["python/pytorch-2.5.1"])
            if ("base64 -d > submit_%s.sh" % nname) not in block or ("jsub < submit_%s.sh" % nname) not in block:
                bad("%s/%s 直接提交块(base64)异常" % (gname, nname))
            try:
                _b64 = block.split('echo "')[1].split('" | base64')[0]
                _decoded = base64.b64decode(_b64).decode("utf-8")
                if _decoded.rstrip("\n") != build_script(g, node, cpus, gpus, "selftest", runbody,
                                                         "48:00", ["python/pytorch-2.5.1"]).rstrip("\n"):
                    bad("%s/%s base64 解码还原不一致" % (gname, nname))
            except Exception:
                bad("%s/%s base64 解码异常" % (gname, nname))
            if g["kind"] in ("GPU", "NPU"):
                if "select[type==LINUX64]" not in script:
                    bad("%s/%s GPU/NPU 脚本应含 -R select" % (gname, nname))
            else:
                if "select[type==LINUX64]" in script:
                    bad("%s/%s CPU 脚本不应含 -R select" % (gname, nname))
            if gpus > 0:
                if "#JSUB -gpgpu %d" % gpus not in script:
                    bad("%s/%s 脚本缺 -gpgpu" % (gname, nname))
            else:
                if "-gpgpu" in script:
                    bad("%s/%s 无GPU节点脚本不应出现 -gpgpu" % (gname, nname))
            if valid_cpu(g, node, cpus + 1):
                bad("%s/%s CPU 超上限未被拦截" % (gname, nname))
            if gpus > 0 and valid_gpu(g, node, gpus + 1):
                bad("%s/%s GPU 超上限未被拦截" % (gname, nname))

    report.insert(0, "西电超算 GPU 切换助手 自测报告  (v%s)" % VERSION)
    report.insert(1, "节点组: %d 个, 节点: %d 个" % (len(RESOURCES), total_nodes))
    manual_ok = len(MANUAL_SECTIONS) > 0
    if not manual_ok:
        bad("内置使用手册内容为空")
    report.append("使用手册: 内置 %d 节 PASS" % len(MANUAL_SECTIONS))

    # ---------- 图标路径：必须运行时推导，不能写死盘符（否则发给别人就读不到）----------
    cands = icon_candidates("icon.ico")
    if not cands or os.path.normpath(cands[-1]) != os.path.normpath(os.path.join(os.getcwd(), "icon.ico")):
        bad("图标候选路径应包含当前目录（相对路径查找）: %r" % (cands,))
    if not any(os.path.isfile(c) for c in cands):
        report.append("图标: 未找到 icon.ico（不影响功能，仅窗口无图标）")
    else:
        report.append("图标: 运行时相对查找可命中 PASS  (%s)" %
                      next(c for c in cands if os.path.isfile(c)))
    try:
        with open(os.path.abspath(__file__), "r", encoding="utf-8") as f:
            code = f.read()
    except Exception:
        code = ""
    if code:
        import re as _re
        if _re.search(r"""['"][A-Za-z]:[\\\\/][^'"]{0,120}icon""", code, _re.I):
            bad("源码里出现了写死盘符的图标路径")
        else:
            report.append("源码: 未发现写死盘符的资源路径 PASS")
        spec = os.path.join(app_dir(), "GPU切换助手.spec")
        if os.path.isfile(spec):
            try:
                with open(spec, "r", encoding="utf-8") as f:
                    spec_txt = f.read()
            except Exception:
                spec_txt = ""
            if _re.search(r"""['"][A-Za-z]:[\\\\/][^'"]{0,120}icon""", spec_txt, _re.I):
                bad("打包配置 spec 里图标是绝对路径，换机器重新打包会失败")
            else:
                report.append("打包配置: spec 图标为相对路径 PASS")

    # ---------- 队列名核对（2026-09-28 在平台 jqueues / jsub 实测） ----------
    verified_queues = {"CPUgroup_X86_xeon8538P_1T": "cpu_x86fat",
                       "CPUgroup_X86_xeon8358P_512G": "cpu_x86thin",
                       "CPUgroup_X86_xeon8358P_256G": "cpu_x86thin",
                       "CPUgroup_X86_xeon8378C_512G": "cpu_x86",
                       "CPUgroup_ARM_kunpeng920_512G": "cpu_arm1",
                       "CPUgroup_ARM_kunpeng920_512G_openEuler": "cpu_arm2",
                       "CPUgroup_ARM_kunpeng920_1T": "cpu_armfat1"}
    for gname, q in verified_queues.items():
        hits = [x for x in RESOURCES if x["group"] == gname]
        if not hits or hits[0]["queue"] != q:
            bad("节点组 %s 的队列应为 %s（平台实测名）" % (gname, q))
    if any(x["queue"] == "cpu_x86_fat" for x in RESOURCES):
        bad("cpu_x86_fat 平台不存在（正确名 cpu_x86fat）")
    report.append("队列名核对: CPU/ARM 组队列与平台 jqueues 一致 PASS")

    # ---------- 界面输入健壮性 ----------
    for v in ("", "abc", None, "12.5", "  ", []):
        if safe_int(v, 7) != 7:
            bad("safe_int(%r) 应返回默认值 7" % (v,))
    if safe_int(" 64 ") != 64 or safe_int(8) != 8 or safe_int(True) != 1:
        bad("safe_int 正常数字解析错误")
    if safe_int("8bc") != 8 or safe_int("64x") != 64:
        bad("safe_int 末尾混入字母时应保留已打对的数字")
    report.append("输入健壮性: safe_int 非数字/空值兜底 PASS")
    if not prefs_path().startswith(os.path.expanduser("~")):
        bad("上次设置应存在用户目录，避免程序目录只读时写失败: %s" % prefs_path())
    else:
        report.append("设置记忆: 存放于用户目录 PASS")

    report.append("结果: %s" % ("通过 PASS" if ok else "存在失败 FAIL"))

    out = "\n".join(report)
    try:
        with open(os.path.join(app_dir(), "gpu_switch_selftest.txt"), "w", encoding="utf-8") as f:
            f.write(out + "\n")
    except Exception:
        pass
    print(out)
    return 0 if ok else 1


def app_dir():
    """程序所在目录（打包后 = exe 所在目录；源码运行 = .py 所在目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def icon_candidates(name="icon.ico"):
    """图标查找顺序：打包临时目录 → 程序所在目录 → 当前目录。
    全部是运行时推导出来的路径，不写死任何盘符，所以整个文件夹拷给别人、换台机器都能取到图标。"""
    paths = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(os.path.join(meipass, name))
    paths.append(os.path.join(app_dir(), name))
    paths.append(os.path.join(os.getcwd(), name))
    out, seen = [], set()
    for p in paths:
        p = os.path.normpath(p)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def resource_path(name):
    """兼容旧调用：返回第一个真实存在的资源路径，都找不到时返回首选位置。"""
    for p in icon_candidates(name):
        if os.path.isfile(p):
            return p
    return icon_candidates(name)[0]


def set_window_icon(win):
    """给窗口设置图标；找不到图标就跳过（不影响功能）。"""
    for p in icon_candidates("icon.ico"):
        if os.path.isfile(p):
            try:
                win.iconbitmap(p)
                return True
            except Exception:
                continue
    return False


def prefs_path():
    """上次使用记录的存放位置：放在用户目录，避免程序被拷到只读位置时写失败。"""
    return os.path.join(os.path.expanduser("~"), ".gpu_switch_helper.json")


def load_prefs():
    try:
        with open(prefs_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_prefs(data):
    try:
        with open(prefs_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def enable_dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def install_exception_handler(root):
    """界面回调里抛出的异常：写日志 + 弹窗提示。
    打包成无控制台 exe 后 sys.stderr 是 None，异常默认会被吞掉，用户只会觉得『点了没反应』。"""
    import tkinter as tk

    def _report(exc_type, value, tb):
        text = "".join(traceback.format_exception(exc_type, value, tb))
        try:
            with open(os.path.join(app_dir(), "切换助手_错误.log"), "a", encoding="utf-8") as f:
                f.write("[%s] %s\n%s\n\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), VERSION, text))
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("界面出现异常", "%s: %s\n\n详情已记录到程序目录的\n切换助手_错误.log"
                                 % (exc_type.__name__, value))
        except tk.TclError:
            pass

    root.report_callback_exception = _report


# ============================================================================
# 主题样式（浅色现代风）
# ============================================================================
def setup_styles(root):
    from tkinter import ttk
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(".", background=BG, foreground=FG, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Banner.TFrame", background=BANNER)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=FG, font=FONT)
    style.configure("Card.TLabel", background=CARD, foreground=FG, font=FONT)
    style.configure("CardHint.TLabel", background=CARD, foreground=FG2, font=FONT_SMALL)
    style.configure("BannerTitle.TLabel", background=BANNER, foreground="#ffffff", font=FONT_TITLE)
    style.configure("BannerSub.TLabel", background=BANNER, foreground="#dbe6ff", font=FONT_SMALL)
    style.configure("Section.TLabel", background=BG, foreground=ACCENT, font=FONT_H)
    style.configure("Info.TLabel", background=BG, foreground=INFO, font=FONT)
    style.configure("CardInfo.TLabel", background=CARD, foreground=INFO, font=FONT_SMALL)
    style.configure("Warn.TLabel", background=BG, foreground=WARN, font=FONT)
    style.configure("Hint.TLabel", background=BG, foreground=FG2, font=FONT_SMALL)
    style.configure("TLabelframe", background=BG, bordercolor=LINE, foreground=ACCENT, font=FONT_H)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT, font=FONT_CARD)
    # 下拉框 / 输入框：卡片内用白色底，卡片外用主题灰底
    for pfx, trough in (("", BG), ("Card.", CARD)):
        style.configure(pfx + "TCombobox", fieldbackground=CARD, background=trough, foreground=FG,
                        arrowcolor=ACCENT, bordercolor=LINE, lightcolor=trough, darkcolor=trough,
                        padding=5, selectbackground=ACCENT, selectforeground="#ffffff")
        style.map(pfx + "TCombobox",
                  fieldbackground=[("readonly", CARD)],
                  foreground=[("readonly", FG)],
                  bordercolor=[("focus", ACCENT)])
    style.configure("TEntry", fieldbackground=CARD, foreground=FG, insertcolor=FG,
                    bordercolor=LINE, lightcolor=BG, darkcolor=BG, padding=4)
    style.configure("Card.TEntry", fieldbackground=CARD, foreground=FG, insertcolor=FG,
                    bordercolor=LINE, lightcolor=CARD, darkcolor=CARD, padding=4)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.map("Card.TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", borderwidth=0,
                    font=FONT_CARD, padding=(16, 8))
    style.map("Accent.TButton",
              background=[("active", ACCENT_HI), ("pressed", ACCENT_DARK)],
              foreground=[("disabled", "#c8d2e8")])
    style.configure("Ghost.TButton", background=CARD2, foreground=FG, borderwidth=0, font=FONT, padding=(14, 8))
    style.map("Ghost.TButton",
              background=[("active", "#d3ddf0"), ("pressed", "#c2cfe6")],
              foreground=[("disabled", "#b6c0d4")])
    # 卡片内部用的小按钮（底色跟卡片标题条一致）
    style.configure("Head.TButton", background="#e8eefb", foreground=ACCENT_DARK, borderwidth=0,
                    font=FONT_SMALL, padding=(12, 5))
    style.map("Head.TButton", background=[("active", "#d7e2f8"), ("pressed", "#c6d5f2")])
    style.configure("CardGhost.TButton", background=CARD2, foreground=FG, borderwidth=0,
                    font=FONT_SMALL, padding=(12, 5))
    style.map("CardGhost.TButton", background=[("active", "#d3ddf0"), ("pressed", "#c2cfe6")],
              foreground=[("disabled", "#b6c0d4")])
    style.configure("Vertical.TScrollbar", background=CARD2, troughcolor=BG, bordercolor=BG, arrowcolor=FG)
    style.configure("Horizontal.TScrollbar", background=CARD2, troughcolor=BG, bordercolor=BG, arrowcolor=FG)

    root.option_add("*TCombobox*Listbox*Background", CARD)
    root.option_add("*TCombobox*Listbox*Foreground", FG)
    root.option_add("*TCombobox*Listbox*Font", FONT)
    root.option_add("*TCombobox*Listbox*selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")


def make_card(parent, title, sub=""):
    """白色卡片容器：左侧蓝色小竖条 + 标题 + 右上角可选说明，返回 (卡片, 内容区, 标题条)。"""
    import tkinter as tk
    card = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightcolor=ACCENT,
                    highlightthickness=1, bd=0)
    head = tk.Frame(card, bg=CARD_HEAD, bd=0)
    head.pack(fill="x")
    tk.Frame(head, bg=ACCENT, width=3, height=20, bd=0, highlightthickness=0).pack(side="left")
    tk.Label(head, text=title, bg=CARD_HEAD, fg=ACCENT_DARK, font=FONT_CARD).pack(
        side="left", padx=(8, 0), pady=6)
    if sub:
        tk.Label(head, text=sub, bg=CARD_HEAD, fg=FG3, font=FONT_SMALL).pack(side="right", padx=(0, 10))
    body = tk.Frame(card, bg=CARD, bd=0)
    body.pack(fill="both", expand=True, padx=10, pady=8)
    return card, body, head


def make_scroll(root, widget):
    from tkinter import ttk
    sb = ttk.Scrollbar(root, command=widget.yview)
    widget.configure(yscrollcommand=sb.set)
    return sb


def open_big_editor(root, title, get_text, set_text, editable):
    """放大窗口：用于运行内容框 / 结果框的放大查看与编辑。"""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    set_window_icon(win)
    banner = ttk.Frame(win, style="Banner.TFrame")
    banner.pack(fill="x")
    ttk.Label(banner, text=title, style="BannerTitle.TLabel").pack(anchor="w", padx=14, pady=(10, 8))

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=8)
    txt = tk.Text(frame, wrap="none", bg=CODE_BG, fg=CODE_FG, insertbackground=FG,
                  selectbackground=ACCENT, selectforeground="#ffffff", relief="flat",
                  highlightthickness=1, highlightbackground=CARD2, highlightcolor=ACCENT,
                  font=FONT_CODE, padx=8, pady=6)
    sb = make_scroll(frame, txt)
    sb.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)
    txt.insert("1.0", get_text() or "")
    if editable:
        txt.bind("<KeyRelease>", lambda e: set_text(txt.get("1.0", "end-1c")))
    else:
        txt.configure(state="disabled")

    row = ttk.Frame(win)
    row.pack(fill="x", pady=(0, 8), padx=10)
    if editable:
        ttk.Button(row, text="同步到主界面", style="Ghost.TButton",
                   command=lambda: set_text(txt.get("1.0", "end-1c"))).pack(side="left")
    else:
        def _refresh():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("1.0", get_text() or "")
            txt.configure(state="disabled")
        ttk.Button(row, text="刷新内容", style="Ghost.TButton", command=_refresh).pack(side="left")
    ttk.Button(row, text="关闭", style="Accent.TButton", command=win.destroy).pack(side="right")

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = max(620, min(win.winfo_reqwidth(), sw - 40))
    h = max(420, min(win.winfo_reqheight(), sh - 60))
    win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max((sh - h) // 2, 0)))


# ============================================================================
# 使用手册：应用内渲染 + 独立窗口
# ============================================================================
def _fmt_table_row(cells, widths):
    return "   " + "   │   ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells))


def render_manual(txt):
    """把 MANUAL_SECTIONS 渲染进带样式标签的 Text 控件。"""
    txt.configure(state="normal")
    txt.delete("1.0", "end")
    for kind, content in MANUAL_SECTIONS:
        if kind == "h1":
            txt.insert("end", "\n" + content + "\n", "h1")
        elif kind == "h2":
            txt.insert("end", "\n" + content + "\n", "h2")
        elif kind == "body":
            txt.insert("end", content + "\n", "body")
        elif kind == "code":
            txt.insert("end", "\n" + content + "\n", "code")
        elif kind == "note":
            txt.insert("end", content + "\n", "note")
        elif kind == "table":
            head = content[0]
            rows = content[1:]
            all_rows = [head] + rows
            widths = [max(len(str(c)) for c in col) for col in zip(*all_rows)]
            txt.insert("end", "\n" + _fmt_table_row(head, widths) + "\n", "thead")
            for r in rows:
                txt.insert("end", _fmt_table_row(r, widths) + "\n", "trow")


def show_manual(root):
    """弹出使用手册窗口（样式跟随应用主题）。"""
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(root)
    win.title("使用手册 · 西电超算")
    win.configure(bg=BG)
    set_window_icon(win)

    banner = ttk.Frame(win, style="Banner.TFrame")
    banner.pack(fill="x")
    ttk.Label(banner, text="西电超算 · 使用手册", style="BannerTitle.TLabel").pack(anchor="w", padx=14, pady=(12, 2))
    ttk.Label(banner, text="平台登录 · 显卡切换 · 调度命令 · 提交作业 · 常见问题", style="BannerSub.TLabel").pack(
        anchor="w", padx=14, pady=(0, 10))

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=8)
    txt = tk.Text(frame, wrap="word", bg=BG, fg=FG, font=FONT, padx=10, pady=6,
                  relief="flat", highlightthickness=1, highlightbackground=CARD2, highlightcolor=ACCENT,
                  cursor="ibeam")
    sb = make_scroll(frame, txt)
    txt.tag_configure("h1", font=("Microsoft YaHei UI", 12, "bold"), foreground=ACCENT, spacing1=10, spacing3=6)
    txt.tag_configure("h2", font=FONT_CARD, foreground=ACCENT_DARK, spacing1=8, spacing3=4)
    txt.tag_configure("body", font=FONT, foreground=FG, spacing1=2, spacing3=4)
    txt.tag_configure("code", background=CODE_BG, foreground=CODE_FG, font=FONT_CODE,
                      spacing1=4, spacing3=8, lmargin1=12, lmargin2=12)
    txt.tag_configure("thead", font=("Consolas", 10, "bold"), foreground=ACCENT, spacing1=4, spacing3=2)
    txt.tag_configure("trow", font=("Consolas", 10), foreground=FG, spacing1=1, spacing3=1)
    txt.tag_configure("note", font=FONT_SMALL, foreground=INFO, spacing1=2, spacing3=6)
    txt.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    render_manual(txt)

    def _copy_selection():
        try:
            s = txt.get("sel.first", "sel.last")
        except tk.TclError:
            s = ""
        if s:
            root.clipboard_clear()
            root.clipboard_append(s)

    def _select_all_text():
        txt.tag_add("sel", "1.0", "end")
        return "break"

    # 手册按普通文本处理：任意处都能用鼠标选中 + Ctrl+C 复制（不拦截按键）
    # 代码块只是颜色样式不同，选中/复制行为与普通文本完全一致
    txt.bind("<Control-c>", lambda e: (_copy_selection(), "break")[1])
    txt.bind("<Control-Key-c>", lambda e: (_copy_selection(), "break")[1])
    txt.bind("<Control-a>", _select_all_text)

    # 右键菜单：复制选中的内容
    ctx_menu = tk.Menu(win, tearoff=0)
    ctx_menu.add_command(label="复制", command=_copy_selection)

    def _popup(e):
        try:
            ctx_menu.tk_popup(e.x_root, e.y_root)
        finally:
            ctx_menu.grab_release()

    txt.bind("<Button-3>", _popup)

    def _copy_all():
        root.clipboard_clear()
        root.clipboard_append(txt.get("1.0", "end-1c"))
        messagebox.showinfo("已复制", "手册全文已复制到剪贴板")

    def _copy_selected():
        try:
            s = txt.get("sel.first", "sel.last")
        except tk.TclError:
            s = ""
        if s:
            root.clipboard_clear()
            root.clipboard_append(s)
            messagebox.showinfo("已复制", "已复制选中内容（%d 字）" % len(s))
        else:
            messagebox.showinfo("提示", "请先用鼠标拖动选中要复制的文字")

    def _copy_code():
        ranges = txt.tag_ranges("code")
        parts = []
        for i in range(0, len(ranges), 2):
            s = txt.get(ranges[i], ranges[i + 1]).strip("\n")
            if s:
                parts.append(s)
        if not parts:
            messagebox.showinfo("提示", "手册中没有代码块")
            return
        root.clipboard_clear()
        root.clipboard_append("\n\n".join(parts))
        messagebox.showinfo("已复制", "已复制手册中全部代码块（%d 段）" % len(parts))

    row = ttk.Frame(win)
    row.pack(fill="x", pady=(0, 8))
    ttk.Button(row, text="复制全文", style="Ghost.TButton", command=_copy_all).pack(side="left", padx=(10, 4))
    ttk.Button(row, text="复制代码", style="Ghost.TButton", command=_copy_code).pack(side="left", padx=4)
    ttk.Button(row, text="复制选中", style="Ghost.TButton", command=_copy_selected).pack(side="left", padx=4)
    ttk.Button(row, text="关闭", style="Accent.TButton", command=win.destroy).pack(side="right", padx=10)

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = min(win.winfo_reqwidth(), sw - 40)
    h = min(win.winfo_reqheight(), sh - 60)
    x = max((sw - w) // 2, 0)
    y = max((sh - h) // 2, 0)
    win.geometry("%dx%d+%d+%d" % (w, h, x, y))


def manual_test():
    """测试：打开使用手册窗口 2.5 秒后自动关闭。"""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    show_manual(root)
    root.after(2500, root.destroy)
    root.mainloop()
    print("MANUAL OK")


# ============================================================================
# 图形界面
# ============================================================================
def run_gui(auto_close=0):
    """构建并进入主界面。auto_close>0 时毫秒后自动关闭（用于 --guismoke 回归测试）。"""
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    root = tk.Tk()
    root.title("西电超算 GPU 切换助手  v%s" % VERSION)
    root.configure(bg=BG)
    set_window_icon(root)
    setup_styles(root)
    install_exception_handler(root)

    group_names = [g["group"] for g in RESOURCES]
    state = {"updating": False}
    prefs = load_prefs()

    # ==================== 顶部横幅 ====================
    banner = tk.Frame(root, bg=BANNER, bd=0)
    banner.pack(fill="x")
    btop = tk.Frame(banner, bg=BANNER, bd=0)
    btop.pack(fill="x", padx=16, pady=(12, 0))
    btn_manual = tk.Button(btop, text="使用手册", bg="#f2f6ff", fg=ACCENT_DARK,
                           activebackground="#ffffff", activeforeground=ACCENT_DARK,
                           relief="flat", bd=0, font=FONT_SMALL, padx=13, pady=4, cursor="hand2")
    btn_manual.pack(side="right", pady=(3, 0))
    tk.Label(btop, text="西电超算 · GPU 切换助手", bg=BANNER, fg="#ffffff", font=FONT_TITLE).pack(side="left")
    tk.Label(btop, text="v" + VERSION, bg=ACCENT_DARK, fg="#eaf1ff", font=FONT_SMALL,
             padx=8, pady=1).pack(side="left", padx=(9, 0), pady=(7, 0))
    tk.Label(banner, text="选节点组 → 选节点 → 定核数 / 时限 → 写运行内容 → 一键生成 jsub 指令与完整提交脚本",
             bg=BANNER, fg="#dbe6ff", font=FONT_SMALL, anchor="w").pack(fill="x", padx=16, pady=(4, 12))

    # ============ 底部状态栏（先 pack，保证不会被主体挤掉）============
    statusbar = tk.Frame(root, bg=STATUS_BG, bd=0)
    statusbar.pack(fill="x", side="bottom")
    tk.Frame(statusbar, bg="#cfdcee", height=1, bd=0).pack(fill="x", side="top")
    status_msg = tk.StringVar(value="就绪：选择节点组后自动生成指令与脚本")
    lbl_status = tk.Label(statusbar, textvariable=status_msg, bg=STATUS_BG, fg=FG2, font=FONT_SMALL,
                          anchor="w", padx=12, pady=6)
    lbl_status.pack(side="left", fill="x", expand=True)
    tk.Label(statusbar, text="快捷键：Ctrl+Enter 生成 ｜ Ctrl+S 保存 ｜ F1 使用手册",
             bg=STATUS_BG, fg=FG3, font=FONT_SMALL, padx=12).pack(side="right")

    def set_status(text, color=FG2):
        status_msg.set(text)
        lbl_status.configure(fg=color)

    # ==================== 主体：左=配置，右=脚本内容 ====================
    body = tk.Frame(root, bg=BG, bd=0)
    body.pack(fill="both", expand=True, padx=12, pady=(10, 8))
    # 左列固定宽度（表单项不该被拉得很宽），右列吃掉剩余空间（代码框需要宽度）
    body.columnconfigure(0, weight=0, minsize=360)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1, minsize=420)

    left = tk.Frame(body, bg=BG, bd=0)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    right = tk.Frame(body, bg=BG, bd=0)
    right.grid(row=0, column=1, sticky="nsew")
    left.rowconfigure(2, weight=1)
    right.rowconfigure(0, weight=10)
    right.rowconfigure(1, weight=11)

    # ---------- ① 节点组 / 节点 ----------
    c1, b1, _h1 = make_card(left, "① 节点组 / 节点", "队列按显卡锁定")
    c1.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
    tk.Label(b1, text="节点组", bg=CARD, fg=FG2, font=FONT_SMALL).pack(anchor="w")
    cbo_group = ttk.Combobox(b1, values=group_names, state="readonly", font=FONT, width=34,
                       style="Card.TCombobox")
    cbo_group.pack(fill="x", pady=(1, 7))
    tk.Label(b1, text="节点（自动带出核数上限）", bg=CARD, fg=FG2, font=FONT_SMALL).pack(anchor="w")
    cbo_node = ttk.Combobox(b1, values=[], state="readonly", font=FONT, width=34, style="Card.TCombobox")
    cbo_node.pack(fill="x", pady=(1, 7))
    info = tk.StringVar(value="请先选择节点组")
    ttk.Label(b1, textvariable=info, style="CardInfo.TLabel", wraplength=330, justify="left").pack(anchor="w")

    # ---------- ② 资源 · 作业名 · 时限 ----------
    c2, b2, _h2 = make_card(left, "② 资源 · 作业名 · 时限", "超上限自动收回")
    c2.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
    g2 = tk.Frame(b2, bg=CARD, bd=0)
    g2.pack(fill="x")
    g2.columnconfigure(0, weight=1)
    g2.columnconfigure(1, weight=1)

    def field(col_label):
        f = tk.Frame(g2, bg=CARD, bd=0)
        tk.Label(f, text=col_label, bg=CARD, fg=FG2, font=FONT_SMALL).pack(anchor="w", pady=(0, 1))
        return f

    f_cpu = field("CPU 核数  -n")
    f_cpu.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
    r_cpu = tk.Frame(f_cpu, bg=CARD, bd=0)
    r_cpu.pack(anchor="w")
    sp_cpu = tk.Spinbox(r_cpu, from_=1, to=1, width=6, bg=CARD, fg=FG, insertbackground=FG,
                        buttonbackground=CARD2, relief="flat", highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=ACCENT, font=FONT_CODE,
                        disabledbackground="#f1f4f9", disabledforeground=FG3)
    sp_cpu.pack(side="left")
    lbl_cpu_max = tk.Label(r_cpu, text="/ 最大 -", bg=CARD, fg=FG3, font=FONT_SMALL)
    lbl_cpu_max.pack(side="left", padx=(6, 0))

    f_gpu = field("GPU 卡数  -gpgpu")
    f_gpu.grid(row=0, column=1, sticky="w", pady=(0, 6))
    r_gpu = tk.Frame(f_gpu, bg=CARD, bd=0)
    r_gpu.pack(anchor="w")
    sp_gpu = tk.Spinbox(r_gpu, from_=1, to=1, width=6, bg=CARD, fg=FG, insertbackground=FG,
                        buttonbackground=CARD2, relief="flat", highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=ACCENT, font=FONT_CODE,
                        disabledbackground="#f1f4f9", disabledforeground=FG3)
    sp_gpu.pack(side="left")
    lbl_gpu_max = tk.Label(r_gpu, text="/ 最大 -", bg=CARD, fg=FG3, font=FONT_SMALL)
    lbl_gpu_max.pack(side="left", padx=(6, 0))

    f_job = field("作业名  -J")
    f_job.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    ent_job = ttk.Entry(f_job, font=FONT, style="Card.TEntry")
    ent_job.pack(fill="x")

    f_time = field("运行时限  -W（选『不限制』则不生成 -W，作业可一直跑）")
    f_time.grid(row=2, column=0, columnspan=2, sticky="ew")
    cbo_time = ttk.Combobox(f_time, values=TIME_OPTIONS, state="readonly", font=FONT, style="Card.TCombobox")
    cbo_time.pack(fill="x")
    cbo_time.current(0)          # 默认『不限制』：不加 -W，作业可一直跑

    # ---------- ③ 环境配置 ----------
    c3, b3, _h3 = make_card(left, "③ 环境配置（module）", "多选")
    c3.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
    lst_env = tk.Listbox(b3, height=4, selectmode="extended", exportselection=False,
                         bg=CARD, fg=FG, selectbackground=ACCENT, selectforeground="#ffffff",
                         font=FONT_SMALL, relief="flat", highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=ACCENT, activestyle="none")
    sb_env = ttk.Scrollbar(b3, command=lst_env.yview)
    lst_env.configure(yscrollcommand=sb_env.set)
    sb_env.pack(side="right", fill="y")
    lst_env.pack(side="left", fill="both", expand=True)
    for _cat, _mods in ENV_MODULES:
        lst_env.insert("end", "—— %s ——" % _cat)
        for _m in _mods:
            lst_env.insert("end", "  %s" % _m)
    for _i in range(lst_env.size()):
        if lst_env.get(_i).startswith("——"):
            lst_env.itemconfig(_i, foreground=FG3, selectforeground=FG3)
    lst_env.see(0)
    env_btns = tk.Frame(c3, bg=CARD, bd=0)
    env_btns.pack(fill="x", padx=10, pady=(6, 8))
    btn_env_default = ttk.Button(env_btns, text="默认推荐", style="CardGhost.TButton")
    btn_env_default.pack(side="left")
    btn_env_clear = ttk.Button(env_btns, text="清空", style="CardGhost.TButton")
    btn_env_clear.pack(side="left", padx=(6, 0))
    tk.Label(env_btns, text="列表外的模块可手动补写；ARM 节点选 -aarch64 版本",
             bg=CARD, fg=FG3, font=FONT_SMALL).pack(side="left", padx=(8, 0))

    # ---------- 操作 ----------
    c4, b4, _h4 = make_card(left, "操作")
    c4.grid(row=3, column=0, sticky="nsew")
    btn_gen = ttk.Button(b4, text="生成指令 / 完整脚本", style="Accent.TButton")
    btn_gen.pack(fill="x", pady=(0, 6))
    row_ops = tk.Frame(b4, bg=CARD, bd=0)
    row_ops.pack(fill="x")
    btn_example = ttk.Button(row_ops, text="载入简单示例", style="CardGhost.TButton")
    btn_example.pack(side="left")
    btn_reset = ttk.Button(row_ops, text="重置", style="CardGhost.TButton")
    btn_reset.pack(side="left", padx=(6, 0))
    tk.Label(row_ops, text="示例约 30 秒", bg=CARD, fg=FG3, font=FONT_SMALL).pack(side="right")

    # ---------- ④ 运行命令 / 脚本 ----------
    c5, b5, h5 = make_card(right, "④ 运行命令 / 脚本")
    c5.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
    btn_max_run = ttk.Button(h5, text="放大编辑", style="Head.TButton")
    btn_max_run.pack(side="right", padx=(6, 10))
    cbo_kind = ttk.Combobox(h5, values=CONTENT_KINDS, state="readonly", width=10,
                            font=FONT_SMALL, style="Card.TCombobox")
    cbo_kind.pack(side="right", padx=(6, 6))
    cbo_kind.current(0)          # 默认『自动识别』
    tk.Label(h5, text="类型", bg=CARD_HEAD, fg=FG2, font=FONT_SMALL).pack(side="right")
    tk.Label(b5, text="写你要在计算节点上执行的内容：单行命令、多行 Shell，或直接贴一段 Python 代码（自动识别并用 python3 执行）。",
             bg=CARD, fg=FG3, font=FONT_SMALL, anchor="w", justify="left").pack(anchor="w", pady=(0, 4))
    txt_run = tk.Text(b5, height=8, width=58, wrap="none", bg=CODE_BG, fg=CODE_FG, insertbackground="#ffffff",
                      selectbackground=ACCENT, selectforeground="#ffffff", relief="flat",
                      highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT,
                      font=FONT_CODE, padx=8, pady=6)
    sb_run = make_scroll(b5, txt_run)
    txt_run.pack(side="left", fill="both", expand=True)
    sb_run.pack(side="right", fill="y")

    # ---------- ⑤ 生成结果 ----------
    c6, b6, h6 = make_card(right, "⑤ 生成结果")
    c6.grid(row=1, column=0, sticky="nsew")
    btn_max_out = ttk.Button(h6, text="放大查看", style="Head.TButton")
    btn_max_out.pack(side="right", padx=(6, 10))
    tk.Label(h6, text="复制整段到集群粘贴回车即提交 ｜ jjobs 看作业 ｜ tail -f output.<作业号> 看日志",
             bg=CARD_HEAD, fg=FG3, font=FONT_SMALL).pack(side="right", padx=(0, 8))
    txt_out = tk.Text(b6, height=8, width=58, wrap="none", bg=CODE_BG, fg=CODE_FG, insertbackground="#ffffff",
                      selectbackground=ACCENT, selectforeground="#ffffff", relief="flat",
                      highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT,
                      font=FONT_CODE, padx=8, pady=6, state="disabled")
    sb_out = make_scroll(b6, txt_out)
    txt_out.pack(side="left", fill="both", expand=True)
    sb_out.pack(side="right", fill="y")
    out_btns = tk.Frame(c6, bg=CARD, bd=0)
    out_btns.pack(fill="x", padx=10, pady=(6, 8))
    btn_copy_cmd = ttk.Button(out_btns, text="复制单行指令", style="CardGhost.TButton")
    btn_copy_cmd.pack(side="left")
    btn_copy_submit = ttk.Button(out_btns, text="复制提交版（粘贴即提交）", style="Accent.TButton")
    btn_copy_submit.pack(side="left", padx=(6, 0))
    btn_save = ttk.Button(out_btns, text="保存 submit.sh", style="CardGhost.TButton")
    btn_save.pack(side="right", padx=(6, 0))

    # 代码框支持：鼠标选中后 Ctrl+C 复制、Ctrl+A 全选（tk Text 默认无此快捷键）
    def _bind_code_copy(wid):
        def _copy(_e):
            try:
                root.clipboard_clear()
                root.clipboard_append(wid.get("sel.first", "sel.last"))
                set_status("✓ 已复制选中内容到剪贴板", INFO)
            except tk.TclError:
                pass
            return "break"

        def _all(_e):
            wid.tag_add("sel", "1.0", "end")
            return "break"

        wid.bind("<Control-c>", _copy)
        wid.bind("<Control-Key-c>", _copy)
        wid.bind("<Control-a>", _all)
        wid.bind("<Control-Key-a>", _all)

    _bind_code_copy(txt_run)
    _bind_code_copy(txt_out)

    # ==================== 逻辑 ====================
    def current_group():
        return find_group(cbo_group.get())

    def current_node():
        g = current_group()
        if not g:
            return None
        return find_node(g, cbo_node.get().split("（")[0].strip())

    def run_text():
        return txt_run.get("1.0", "end").strip("\n")

    def time_limit():
        return cbo_time.get()

    def refresh_group(event=None):
        g = current_group()
        if not g:
            return
        cbo_node["values"] = ["%s（CPU %d核 / GPU %d卡）" % (n[0], n[1], n[2]) for n in g["nodes"]]
        cbo_node.current(0)
        refresh_node()

    def refresh_node(event=None):
        g = current_group()
        n = current_node()
        if not g or not n:
            return
        state["updating"] = True
        try:
            nname, cpus, gpus = n
            sp_cpu.configure(to=cpus, state="normal")
            v = safe_int(sp_cpu.get(), 0)
            if v < 1 or v > cpus:
                sp_cpu.delete(0, "end")
                sp_cpu.insert(0, str(cpus))
            lbl_cpu_max.configure(text="/ 最大 %d" % cpus)
            if gpus > 0:
                sp_gpu.configure(to=gpus, state="normal")
                v = safe_int(sp_gpu.get(), 0)
                if v < 1 or v > gpus:
                    sp_gpu.delete(0, "end")
                    sp_gpu.insert(0, "1")
                lbl_gpu_max.configure(text="/ 最大 %d" % gpus)
            else:
                sp_gpu.configure(state="disabled")
                sp_gpu.delete(0, "end")
                sp_gpu.insert(0, "0")
                lbl_gpu_max.configure(text="（本节点无 GPU）")
            info.set("节点 %s ｜ CPU 上限 %d 核 ｜ GPU 上限 %d 卡 ｜ 队列：%s%s" % (
                nname, cpus, gpus, g["queue"], ("" if gpus else "（GPU 不可用）")))
        finally:
            state["updating"] = False
        generate()

    def clamp_value(spin, lo, hi):
        v = max(lo, min(hi, safe_int(spin.get(), lo)))
        if str(v) != spin.get():
            spin.delete(0, "end")
            spin.insert(0, str(v))
        return v

    def env_select(mods):
        lst_env.selection_clear(0, lst_env.size() - 1)
        for i in range(lst_env.size()):
            if lst_env.get(i).strip() in mods:
                lst_env.selection_set(i)
        generate()

    def env_selected():
        mods = []
        for i in lst_env.curselection():
            t = lst_env.get(i)
            if not t.startswith("——"):
                mods.append(t.strip())
        return mods

    def build_output():
        g = current_group()
        n = current_node()
        if not g or not n:
            return "请先选择节点组和节点"
        cpu = clamp_value(sp_cpu, 1, n[1])
        gpu = clamp_value(sp_gpu, 1, n[2]) if n[2] > 0 else 0
        job = ent_job.get().strip() or "my_job"
        tlim = time_limit()
        content = run_text() or "python3 train.py"
        kd = resolve_content_kind(cbo_kind.get(), content)
        # 单行 jsub 只适用于 shell 命令；单行 Python 代码需走 base64 提交版（否则会被 shell 直接执行报错）
        single = run_content_is_single_line(content) and kd == "shell"
        out = []
        if single:
            out.append("【单行 jsub 指令】")
            out.append(build_command(g, n, cpu, gpu, job, content, tlim))
            out.append("")
        else:
            out.append("【运行内容是多行 / Python → 请用下面的“直接提交版”】")
            out.append("")
        out.append("【直接提交版：整段脚本已编码为一行 base64，粘贴到集群不会丢字、不会错位】")
        out.append(build_submit_block(g, n, cpu, gpu, job, content, tlim, env_selected(), kd).rstrip("\n"))
        return "\n".join(out)

    def txt_out_clear_set(text):
        txt_out.configure(state="normal")
        txt_out.delete("1.0", "end")
        txt_out.insert("1.0", text)
        txt_out.configure(state="disabled")

    def generate(*_):
        if state["updating"]:
            return
        g = current_group()
        if not g:
            txt_out_clear_set("请先选择节点组和节点")
            set_status("请先选择节点组和节点", FG2)
            return
        n = current_node()
        if n and not g["queue_confirmed"]:
            set_status("⚠ 已生成，但队列「%s」未确认：提交前请用 jqueues -u $USER 核对" % g["queue"], WARN)
        elif n:
            set_status("✓ 已生成：%s ｜ 队列 %s ｜ CPU %d 核 ｜ GPU %s 卡 ｜ 时限 %s" % (
                n[0], g["queue"], clamp_value(sp_cpu, 1, n[1]),
                (clamp_value(sp_gpu, 1, n[2]) if n[2] > 0 else 0), time_limit()), INFO)
        else:
            set_status("请选择节点", FG2)
        txt_out_clear_set(build_output())

    def on_value_change(*_):
        if not state["updating"]:
            generate()

    sp_cpu_sv = tk.StringVar(value="8")
    sp_cpu.configure(textvariable=sp_cpu_sv, command=lambda: generate())
    sp_cpu_sv.trace_add("write", on_value_change)
    sp_gpu_sv = tk.StringVar(value="1")
    sp_gpu.configure(textvariable=sp_gpu_sv, command=lambda: generate())
    sp_gpu_sv.trace_add("write", on_value_change)

    ent_job_var = tk.StringVar(value="my_job")
    ent_job.configure(textvariable=ent_job_var)
    ent_job_var.trace_add("write", on_value_change)

    cbo_time.bind("<<ComboboxSelected>>", generate)
    cbo_kind.bind("<<ComboboxSelected>>", generate)
    txt_run.bind("<KeyRelease>", lambda e: generate())
    cbo_group.bind("<<ComboboxSelected>>", refresh_group)
    cbo_node.bind("<<ComboboxSelected>>", refresh_node)
    btn_gen.configure(command=lambda: generate())
    btn_env_default.configure(command=lambda: env_select(ENV_DEFAULT))
    btn_env_clear.configure(command=lambda: env_select([]))
    lst_env.bind("<<ListboxSelect>>", lambda e: generate())
    btn_example.configure(command=lambda: (txt_run.delete("1.0", "end"), txt_run.insert("1.0", EXAMPLE_TEXT),
                                           generate(), set_status("已载入简单示例（约 30 秒跑完）", INFO)))

    def pick_default_group():
        """首次进入 / 重置时停在第一个 GPU 组：这个软件主要就是用来切显卡的。"""
        for i, g in enumerate(RESOURCES):
            if g["kind"] == "GPU":
                cbo_group.current(i)
                return
        cbo_group.current(0)

    def reset_all():
        txt_run.delete("1.0", "end")
        cbo_kind.current(0)
        cbo_time.current(0)
        ent_job_var.set("my_job")
        sp_cpu_sv.set("8")
        sp_gpu_sv.set("1")
        lst_env.selection_clear(0, lst_env.size() - 1)
        pick_default_group()
        refresh_group()
        save_prefs({})
        set_status("已重置为默认设置（下次启动也用默认）", INFO)

    def copy_command():
        g = current_group()
        n = current_node()
        if not g or not n:
            messagebox.showwarning("提示", "请先选择节点组和节点")
            return
        content = run_text() or "python3 train.py"
        if not run_content_is_single_line(content) or resolve_content_kind(cbo_kind.get(), content) != "shell":
            messagebox.showwarning("提示", "当前运行内容是多行 / Python，请用「复制提交版」或「保存 submit.sh」")
            return
        cpu = clamp_value(sp_cpu, 1, n[1])
        gpu = clamp_value(sp_gpu, 1, n[2]) if n[2] > 0 else 0
        job = ent_job.get().strip() or "my_job"
        cmd = build_command(g, n, cpu, gpu, job, content, time_limit())
        root.clipboard_clear()
        root.clipboard_append(cmd)
        set_status("✓ 单行 jsub 指令已复制到剪贴板", INFO)

    def copy_submit():
        g = current_group()
        n = current_node()
        if not g or not n:
            messagebox.showwarning("提示", "请先选择节点组和节点")
            return
        cpu = clamp_value(sp_cpu, 1, n[1])
        gpu = clamp_value(sp_gpu, 1, n[2]) if n[2] > 0 else 0
        job = ent_job.get().strip() or "my_job"
        content = run_text()
        kd = resolve_content_kind(cbo_kind.get(), content)
        block = build_submit_block(g, n, cpu, gpu, job, content, time_limit(), env_selected(), kd)
        root.clipboard_clear()
        root.clipboard_append(block)
        set_status("✓ 提交版已复制到剪贴板：到集群粘贴回车 → 自动建脚本 + dos2unix + 提交", INFO)

    def save_script():
        g = current_group()
        n = current_node()
        if not g or not n:
            messagebox.showwarning("提示", "请先选择节点组和节点")
            return
        cpu = clamp_value(sp_cpu, 1, n[1])
        gpu = clamp_value(sp_gpu, 1, n[2]) if n[2] > 0 else 0
        job = ent_job.get().strip() or "my_job"
        content = run_text()
        kd = resolve_content_kind(cbo_kind.get(), content)
        script = build_script(g, n, cpu, gpu, job, content, time_limit(), env_selected(), kd)
        path = filedialog.asksaveasfilename(
            parent=root,
            title="保存提交脚本",
            initialfile="submit_%s.sh" % n[0],
            defaultextension=".sh",
            filetypes=[("Shell 脚本", "*.sh"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(script)
            set_status("✓ 已保存：%s" % path, INFO)
            messagebox.showinfo("已保存", "脚本已保存到：\n%s\n\n提交：jsub < %s\n（上传前先 dos2unix）" % (
                path, os.path.basename(path)))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    btn_manual.configure(command=lambda: show_manual(root))
    btn_copy_cmd.configure(command=copy_command)
    btn_copy_submit.configure(command=copy_submit)
    btn_save.configure(command=save_script)
    btn_reset.configure(command=reset_all)
    btn_max_run.configure(command=lambda: open_big_editor(
        root, "运行命令 / 脚本（放大编辑 · 改动自动同步）",
        lambda: txt_run.get("1.0", "end-1c"),
        lambda s: (txt_run.delete("1.0", "end"), txt_run.insert("1.0", s), generate()),
        True))
    btn_max_out.configure(command=lambda: open_big_editor(
        root, "生成结果（直接提交版 · 放大查看）",
        lambda: txt_out.get("1.0", "end-1c"),
        None, False))

    # ---------- 快捷键 ----------
    for _seq, _fn in (("<Control-Return>", lambda e: (generate(), "break")[1]),
                      ("<Control-KP_Enter>", lambda e: (generate(), "break")[1]),
                      ("<Control-s>", lambda e: (save_script(), "break")[1]),
                      ("<Control-S>", lambda e: (save_script(), "break")[1]),
                      ("<F1>", lambda e: (show_manual(root), "break")[1])):
        try:
            root.bind(_seq, _fn)
        except tk.TclError:
            pass      # 个别系统上键名不可用时跳过，不能让程序因此打不开

    # ---------- 记住上次的设置（存在用户目录，与程序位置无关）----------
    def collect_prefs():
        return {"version": VERSION,
                "group": cbo_group.get(), "node": cbo_node.get(),
                "cpu": sp_cpu.get(), "gpu": sp_gpu.get(), "job": ent_job.get(),
                "time": cbo_time.get(), "kind": cbo_kind.get(),
                "env": env_selected(), "content": txt_run.get("1.0", "end-1c")}

    def on_close():
        try:
            save_prefs(collect_prefs())
        except Exception:
            pass
        root.destroy()

    def apply_prefs(p):
        """恢复上次配置。任何一项取不到或越界都退回默认值，不会因为配置文件坏掉而打不开程序。"""
        try:
            txt_run.insert("1.0", str(p.get("content") or ""))
            if p.get("kind") in CONTENT_KINDS:
                cbo_kind.set(p["kind"])
            if p.get("time") in TIME_OPTIONS:
                cbo_time.set(p["time"])
            if p.get("job"):
                ent_job_var.set(str(p["job"]))
            if p.get("group") in group_names:
                cbo_group.set(p["group"])
            else:
                pick_default_group()
            refresh_group()
            g, n = current_group(), current_node()
            if n and p.get("node") in list(cbo_node["values"]):
                cbo_node.set(p["node"])
                refresh_node()
                n = current_node()
            if n:
                sp_cpu_sv.set(str(max(1, min(n[1], safe_int(p.get("cpu"), n[1])))))
                if n[2] > 0:
                    sp_gpu_sv.set(str(max(1, min(n[2], safe_int(p.get("gpu"), 1)))))
            env_select([m for m in (p.get("env") or []) if isinstance(m, str)])
        except Exception:
            pick_default_group()
            refresh_group()

    root.protocol("WM_DELETE_WINDOW", on_close)
    if prefs:
        apply_prefs(prefs)
    else:
        pick_default_group()
        refresh_group()

    # ---------- 窗口尺寸：按屏幕自适应并居中 ----------
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    # 按界面实际需要的大小开窗（高分屏 / 大字号时自动变大），但不超过屏幕
    win_w = int(max(980, min(root.winfo_reqwidth() + 40, sw - 40)))
    win_h = int(max(620, min(root.winfo_reqheight() + 30, sh - 50)))
    root.geometry("%dx%d+%d+%d" % (win_w, win_h,
                                   max((sw - win_w) // 2, 0), max((sh - win_h) // 2 - 10, 0)))
    root.minsize(980, 640)

    if auto_close:
        root.after(int(auto_close), root.destroy)
    root.mainloop()
    if auto_close:
        print("GUISMOKE OK  (窗口 %s ms 后自动关闭，界面构建无异常)" % auto_close)


def smoke():
    import tkinter as tk
    root = tk.Tk()
    root.title("冒烟测试")
    tk.Label(root, text="GUI 构建 OK，2 秒后自动关闭").pack(padx=40, pady=40)
    root.after(2000, root.destroy)
    root.mainloop()
    print("GUI OK")


def gui_smoke(ms=2200):
    """真正走一遍界面构建（含所有控件、样式、快捷键、上次设置恢复），有问题会直接抛出来。"""
    enable_dpi()
    run_gui(auto_close=ms)


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        sys.exit(selftest())
    if "--smoke" in args:
        smoke()
        sys.exit(0)
    if "--guismoke" in args:
        gui_smoke()
        sys.exit(0)
    if "--manualtest" in args:
        manual_test()
        sys.exit(0)
    enable_dpi()
    try:
        run_gui()
    except Exception:
        try:
            with open(os.path.join(app_dir(), "切换助手_错误.log"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
