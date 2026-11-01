#!/bin/bash
# 修 Realtek 驱动的 mallinfo() 崩溃（在开发 VM 里跑）。
#
# 背景（2026-10-31 真机）：
#   drivers/platform/realtek_ieee80211/os/customer_rtos/customer_rtos_service.c
#   里的 _freertos_GetFreeHeapSize() 调用 mallinfo()；NuttX 的 mallinfo()
#   **不拿堆锁**就遍历整个用户堆。wifi_on / 每次分配都会调它，若与其它线程的
#   malloc/free 并发，遍历到一半堆被改动 → data abort（backtrace 进 mm_foreach）。
#   该返回值只用于内存统计日志，改为固定值即可，不参与功能决策。
#
# 用法（VM 内）：
#   bash tools/patch_realtek_freeheap.sh [vela_root]
#   默认 vela_root：~/vela-opensource，其次按 manifest 软链位置推断。
#
# 幂等：已有 PATCH(contest2026_151) 标记时只打印提示。
set -e

if [ -n "$1" ]; then
    VELA_ROOT="$1"
elif [ -d "$HOME/vela-opensource" ]; then
    VELA_ROOT="$HOME/vela-opensource"
else
    VELA_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
fi

SRC="$VELA_ROOT/nuttx/drivers/platform/realtek_ieee80211/os/customer_rtos/customer_rtos_service.c"

if [ ! -f "$SRC" ]; then
    echo "找不到 $SRC" >&2
    exit 1
fi

if grep -q "PATCH(contest2026_151)" "$SRC"; then
    echo "已打过补丁：$SRC"
    exit 0
fi

python3 - "$SRC" <<'PY'
import re
import sys

path = sys.argv[1]
src = open(path).read()

old = """static u32 _freertos_GetFreeHeapSize(void)
{
\tstruct mallinfo mem;
\tmem = mallinfo();
\treturn mem.arena;
}"""

new = """static u32 _freertos_GetFreeHeapSize(void)
{
\t/* PATCH(contest2026_151): mallinfo() walks the whole heap without the MM
\t * lock. The wifi driver calls this during wifi_on and on every allocation,
\t * which races with other tasks and causes a data abort in mm_foreach
\t * (observed on hardware 2026-10-31). This value is only used for
\t * memory-usage logging, so return a fixed conservative estimate instead
\t * of walking the heap. */
\treturn 16 * 1024 * 1024;
}"""

if old not in src:
    print("未匹配到原始函数，未修改：" + path, file=sys.stderr)
    sys.exit(2)

open(path, "w").write(src.replace(old, new, 1))
print("已打补丁：" + path)
PY
