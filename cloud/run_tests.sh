#!/usr/bin/env bash
#
# 云端单元测试总入口 —— 本地与 CI 共用这一份，两边的判据不会漂。
#
# 只跑**纯单测**：不需要 MIMO_API_KEY、不需要网络、不调任何外部 API、不装任何
# 第三方包（全部只用标准库，与 requirements.txt 里的服务依赖无关）。
#
# 因此 cloud/test_services.py **刻意不在**这里跑 —— 它不是单测，是联网集成脚本：
# 真的会调 ASR/TTS、需要 key、还会在 cloud/ 下生成两个测试 wav（已 gitignore）。
# 把它放进来，CI 必然红，而红的原因和代码质量无关。
set -u

cd "$(dirname "$0")" || exit 1

# 显式清掉 key：证明这些测试与它无关，也防止将来有人不小心把联网调用写进单测
# 却因为本地恰好有 key 而一直是绿的。
unset MIMO_API_KEY

fail=0
total=0

for file in test_*.py; do
    case "$file" in
        test_services.py) continue ;;
    esac
    total=$((total + 1))
    echo "=== $file ==="
    if ! python3 "$file"; then
        fail=$((fail + 1))
    fi
    echo
done

if [ "$total" -eq 0 ]; then
    echo "没有找到任何测试文件（目录：$(pwd)）" >&2
    exit 1
fi

if [ "$fail" -ne 0 ]; then
    echo "❌ $fail / $total 个测试文件失败" >&2
    exit 1
fi

echo "✅ $total 个测试文件全部通过"
