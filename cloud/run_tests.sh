#!/usr/bin/env bash
#
# 云端单元测试总入口 —— 本地与 CI 共用这一份，两边的判据不会漂。
#
# 分两档：
#
#   【纯单测】始终跑。不需要 MIMO_API_KEY、不需要网络、不装任何第三方包
#       （全部只用标准库，与 requirements.txt 里的服务依赖无关）。
#
#   【路由测试】装了 Flask 才跑。test_routes.py 用 Flask 自带的 test client 走
#       进程内 HTTP 往返，验路由注册 / 内存优先磁盘兜底 / 导出这些**接线层** ——
#       模块单测照不到那里。它需要 requirements.txt 里的 Flask 与 openai。
#       没装依赖时**大声跳过**，不是静默跳过：静默跳过正是 §11.25 记下的教训
#       （rehearsal.py 全链路失败时各判据照样通过、仍打印 ✅）。装在不在，输出里
#       一眼能看见。
#
# **刻意不在这里跑**的：cloud/test_services.py —— 它不是单测，是联网集成脚本：
# 真的会调 ASR/TTS、需要 key、还会在 cloud/ 下生成两个测试 wav（已 gitignore）。
# 把它放进来，CI 必然红，而红的原因和代码质量无关。
#
# 用法：
#   bash cloud/run_tests.sh                              # 有依赖就两档全跑
#   pip install -r cloud/requirements.txt                # 想把路由测试一起跑上
#   PYTHON=./.venv/Scripts/python.exe bash run_tests.sh  # Windows 上指定 venv
set -u

cd "$(dirname "$0")" || exit 1

# 解释器解析。
# 为什么不能写死 `python3`：Windows 上新工作模式用的是 cloud/.venv，而 Git Bash 里
# 的 `python3` 会解析到微软商店那个占位程序（跑起来是提示去装 Python，退出码 9009）。
# 所以按 PYTHON 环境变量 → python3 → python 的顺序找一个**真能跑**的。
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "" >/dev/null 2>&1; then
            PY="$cand"
            break
        fi
    done
fi
if [ -z "$PY" ]; then
    echo "找不到可用的 python（可显式指定：PYTHON=/path/to/python bash run_tests.sh）" >&2
    exit 1
fi

# 显式给了 PYTHON 却跑不起来时**当场报错**，不要放它过去：否则每个测试文件都会
# 失败，输出长得像"6 个测试全红"，把排查方向带偏（作者自己踩过一次）。
# ⚠️ 本脚本在解析 PY 之前已经 cd 到 cloud/，所以相对路径以 **cloud/** 为基准。
if ! "$PY" -c "" >/dev/null 2>&1; then
    echo "PYTHON 指定的解释器跑不起来：$PY" >&2
    echo "（本脚本会先 cd 到 cloud/，相对路径以 cloud/ 为基准）" >&2
    exit 1
fi

# 显式清掉 key：证明这些测试与它无关，也防止将来有人不小心把联网调用写进单测
# 却因为本地恰好有 key 而一直是绿的。
unset MIMO_API_KEY

# 路由测试要不要跑，取决于这两个包在不在（numpy/soundfile 是 TTS 的惰性导入，
# 本脚本不会走到，所以不查）。
have_deps=0
if "$PY" -c "import flask, openai" >/dev/null 2>&1; then
    have_deps=1
fi

fail=0
total=0
skipped=0

for file in test_*.py; do
    case "$file" in
        test_services.py) continue ;;
        test_routes.py|test_report_retry.py)
            # 这两个都 import 了带第三方依赖的模块（test_routes 起 Flask app，
            # test_report_retry 走 llm_service→openai），所以归同一档。
            if [ "$have_deps" -eq 0 ]; then
                echo "=== $file ==="
                echo "⚠️  跳过：未装 Flask / openai。"
                echo "    想连它一起跑：pip install -r requirements.txt"
                echo
                skipped=$((skipped + 1))
                continue
            fi
            ;;
    esac
    total=$((total + 1))
    echo "=== $file ==="
    if ! "$PY" "$file"; then
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

if [ "$skipped" -ne 0 ]; then
    echo "✅ $total 个测试文件全部通过（另有 $skipped 个因缺依赖被跳过，见上）"
else
    echo "✅ $total 个测试文件全部通过"
fi
