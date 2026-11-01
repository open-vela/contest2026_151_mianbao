#!/bin/bash
# 让板子开机自动运行 ai_interview（在开发 VM 里跑）。
#
# 背景：NuttX 的 nsh 在 ETC_ROMFS 打开时会执行 /etc/init.d/rcS。这块板子的
# rcS 原来是空的，所以每次上电都停在 nsh> 提示符，要手敲 ai_interview。
# 本脚本往 rcS 末尾加一行启动命令；主程序自己会在没有 Wi-Fi 凭据时
# 从串口提示输入，所以用户开机只需要看串口。
#
# 用法（VM 内）：
#   bash tools/apply_boot_autostart.sh [vela_root]
#   vela_root 默认 ~/vela-opensource
#
# 幂等：已经有启动行时只打印提示，不重复添加。
set -e

if [ -n "$1" ]; then
    VELA_ROOT="$1"
elif [ -d "$HOME/vela-opensource" ]; then
    VELA_ROOT="$HOME/vela-opensource"
else
    # 通过 manifest 软链进来时：<workspace>/packages/demos/<repo>/tools
    VELA_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
fi

RCS="$VELA_ROOT/vendor/allwinnertech/boards/r528/r528s3-velaevb1/src/etc/init.d/rcS"

if [ ! -f "$RCS" ]; then
    echo "找不到 $RCS" >&2
    exit 1
fi

if grep -q "Starting ai_interview" "$RCS"; then
    echo "已配置过：$RCS"
    exit 0
fi

cat >> "$RCS" <<'EOF'

/* 2026-10-31: 上电自动运行作品主程序。
 * 首次没有 Wi-Fi 凭据时，主程序会在这里的串口提示输入热点名和密码；
 * 之后每次上电自动连网并进入待机页。
 *
 * ⚠️ 必须防重入：nsh 每次启动都会执行 rcS（调试 shell、被 spawn 的命令都算），
 * 没有这个 /tmp 标记会不断再启动一个主程序，串口无限刷 NuttShell。
 * /tmp 是 tmpfs，每次开机重建，不需要手动清理。 */
if [ -f /tmp/ai_interview_started ]; then
  echo "ai_interview already started, skip autostart"
else
  echo started > /tmp/ai_interview_started
  echo "Starting ai_interview ..."
  ai_interview
fi
EOF

echo "已追加开机自启：$RCS"
