#!/bin/bash
#
# 提交前清洗仓库里的密钥
#
# 背景：一旦提交并推送，密钥就进了 git 历史 —— 之后删文件也删不掉，只能轮换。
# 本项目的 MIMO_API_KEY 就这样泄露过两次提交（812a1b5、f948ff7，涉及 cloud/ 下
# 4 个文件），至今仍能在官方公开仓的那两个提交里读到。历史擦不掉，唯一的补救是轮换。
#
# ⚠️ 扫描范围在 2026-09-29 从 logs/ 改成**全仓** —— 这个改动本身就是一次纠错：
# 当年真正泄露的那次根本不在 logs/ 里，而在 cloud/ 的源码和文档里，只扫 logs 的
# 旧版本当初就拦不住它。现在 logs/ 目录已经删掉了（比赛结束，见 .gitignore）。
#
# 用法：
#   tools/redact_secrets.sh           清洗（**就地修改**全仓被跟踪的文本文件）
#   tools/redact_secrets.sh --check   只检查不修改；发现疑似密钥返回 1
#
# 它按**特征**匹配，不依赖具体密钥值，因此换成新 key 也不用改脚本。
# 文件清单取自 `git ls-files`（即"会被提交的那些"），二进制文件由 grep -I 自动跳过。
#
set -u

cd "$(dirname "$0")/.." || exit 1

# 按特征匹配而非写死密钥。当前覆盖：
#   sk- 开头 + 24 位以上字母数字 —— 小米 MIMO / OpenAI / DeepSeek 等都长这样
# 以后接入别的服务，在下面追加一条即可。
PATTERN='sk-[A-Za-z0-9]{24,}'
PLACEHOLDER='<REDACTED-API-KEY>'

mode="${1:-redact}"
total=0

while IFS= read -r -d '' f; do
    # grep -I：二进制文件直接跳过 —— 既避免误报，也避免下一步的 sed 改坏二进制
    n=$(grep -oIE "$PATTERN" "$f" 2>/dev/null | wc -l)
    [ "$n" -eq 0 ] && continue

    total=$((total + n))

    if [ "$mode" = "--check" ]; then
        printf '  %4d 处  %s\n' "$n" "$f"
    else
        sed -i -E "s/${PATTERN}/${PLACEHOLDER}/g" "$f"
        printf '  已清洗 %4d 处  %s\n' "$n" "$f"
    fi
done < <(git ls-files -z 2>/dev/null)

if [ "$mode" = "--check" ]; then
    if [ "$total" -gt 0 ]; then
        echo
        echo "发现 $total 处疑似密钥 —— 提交前请先运行： tools/redact_secrets.sh"
        exit 1
    fi
    echo "全仓干净：没有发现疑似密钥"
    exit 0
fi

if [ "$total" -eq 0 ]; then
    echo "全仓干净：没有发现疑似密钥，无需修改"
else
    echo
    echo "共清洗 $total 处。若是在日志/文档里，注意核对改完的语义是否还通顺。"
fi
