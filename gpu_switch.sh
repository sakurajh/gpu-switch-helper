#!/bin/bash
# ============================================================================
#  西电超算 · GPU 切换助手  (gpu_switch.sh)
#  用法: 在登录节点执行  bash gpu_switch.sh
#  功能: 选择显卡 -> 输入 CPU 核数 / GPU 卡数 -> 生成 jsub 提交命令 / 脚本
#  提示: 提交前先确认队列权限:  jqueues -u "$USER"
#        节点组/队列名以平台实际输出为准
# ============================================================================

declare -a GPUS=(
  "RTX 4090        | GPUgroup_X86_e0n6530_1T_4090   | gpu_4090"
  "RTX 6000 Ada    | GPUgroup_X86_e0n6530_1T_6000ada | gpu_6000ada"
  "H100            | GPUgroup_X86_e0n6530_1T_H100    | gpu_h800"
  "A800            | GPUgroup_X86_e0n8358P_1T_A800   | gpu_a800"
  "Ascend 910A     | GPUgroup_X86_e0n8558p_1T_910A   | QUEUE_UNKNOWN"
  "H200            | GPUgroup_X86_e0n8558p_2T_h200   | gpu_h200"
  "RTX PRO 6000    | GPUgroup_X86_e0n8558p_2T_PR06000 | QUEUE_UNKNOWN"
  "Ascend 910C     | npu_910C                        | QUEUE_UNKNOWN"
)

echo "=============================================================="
echo "  西电超算 · GPU 切换助手"
echo "=============================================================="
echo ""
echo "  可选显卡组:"
echo "  ----------------------------------------------------------"
for i in "${!GPUS[@]}"; do
  printf "   [%d] %s\n" "$((i+1))" "${GPUS[$i]}"
done
echo "   [$(( ${#GPUS[@]} + 1 ))] 退出"
echo ""

choice=""
while :; do
  read -rp "  请选择显卡编号 [1-${#GPUS[@]}]，直接回车默认 1: " choice
  choice="${choice:-1}"
  if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#GPUS[@]} )); then
    break
  fi
  if [[ "$choice" == "$(( ${#GPUS[@]} + 1 ))" ]]; then
    echo "  已退出。"; exit 0
  fi
  echo "  输入无效，请重新输入。"
done

idx=$((choice-1))
IFS='|' read -r gpu_name node_group queue <<< "${GPUS[$idx]}"
gpu_name=$(echo "$gpu_name" | xargs)
node_group=$(echo "$node_group" | xargs)
queue=$(echo "$queue" | xargs)

echo ""
echo "  你选择了: $gpu_name"
echo "    节点组 : $node_group"
echo "    队列   : $queue"
if [[ "$queue" == "QUEUE_UNKNOWN" ]]; then
  echo "    ⚠ 队列名未在手册中给出，请先运行: jqueues -u \"\$USER\" 确认后手动替换下面命令中的 <队列>"
fi
echo ""

ncpu=""
while :; do
  read -rp "  CPU 核数 -n [默认 8，上限用 jhosts -l <节点名> 查询]: " ncpu
  ncpu="${ncpu:-8}"
  [[ "$ncpu" =~ ^[0-9]+$ ]] && break
  echo "  请输入数字。"
done

ngpu=""
while :; do
  read -rp "  GPU 卡数 -gpgpu [默认 1，常见 1~8]: " ngpu
  ngpu="${ngpu:-1}"
  [[ "$ngpu" =~ ^[0-9]+$ ]] && break
  echo "  请输入数字。"
done

jname=""
read -rp "  作业名 -J [默认 my_gpu_job]: " jname
jname="${jname:-my_gpu_job}"

run=""
read -rp "  作业运行命令 [默认 python3 train.py]: " run
run="${run:-python3 train.py}"

# 队列名: QUEUE_UNKNOWN -> <队列>
qout="$queue"
[[ "$qout" == "QUEUE_UNKNOWN" ]] && qout="<队列>"

echo ""
echo "  ==============================================================="
echo "  生成的 jsub 命令:"
echo "  ---------------------------------------------------------------"
cmd="jsub -n $ncpu -gpgpu $ngpu -q $qout -m $node_group -J $jname -o output.%J -e error.%J \"$run\""
echo "  $cmd"
echo "  ==============================================================="
echo ""

SCRIPT_GEN=0
sf="submit_${gpu_name// /_}.sh"
ans=""
read -rp "  是否同时生成作业脚本 $sf ? [y/N]: " ans
case "$ans" in
  y|Y|yes|YES)
    {
      echo "#!/bin/bash"
      echo "#JSUB -q $qout"
      echo "#JSUB -m $node_group"
      echo "#JSUB -gpgpu $ngpu"
      echo "#JSUB -n $ncpu"
      echo "#JSUB -o output.%J"
      echo "#JSUB -e error.%J"
      echo "#JSUB -W 48:00"
      echo "#JSUB -J $jname"
      echo ""
      echo "module purge"
      echo "module load cuda/12.6      # 按需修改, module avail 查看"
      echo "module load pytorch/2.5.1  # 按需修改"
      echo "$run"
    } > "$sf"
    chmod +x "$sf" 2>/dev/null
    echo "  ✅ 已生成脚本: $sf"
    echo "     提交方式: jsub < $sf   (Windows 上传前先 dos2unix $sf)"
    SCRIPT_GEN=1
    ;;
  *) echo "  好的，未生成脚本。";;
esac

echo ""
echo "  后续操作:"
if [[ "$SCRIPT_GEN" == "1" ]]; then
  echo "  1) 提交: jsub < $sf   (或用上面的命令行，二选一)"
else
  echo "  1) 提交: 直接执行上面的 jsub 命令"
fi
echo "  2) 看作业: jjobs ; 看日志: tail -f output.<作业号>"
echo "  3) 换卡: 重新运行 bash gpu_switch.sh 即可"
echo ""
