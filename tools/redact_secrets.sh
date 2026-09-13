#!/bin/bash
#
# 提交前清洗 AI Coding 日志里的密钥
#
# 背景：logs/ 目录要随作品一起提交，而对话记录里难免出现 API key。
# 一旦提交并推送，密钥就进了 git 历史 —— 之后删文件也删不掉，只能轮换。
# 本项目的 MIMO_API_KEY 已经这样泄露过一次（commit 812a1b5）。
#
# 所以每次提交前跑一遍这个脚本。它按**特征**匹配，不依赖具体密钥值，
# 因此换成新 key 也不用改脚本。
#
# 用法：
#   tools/redact_secrets.sh           清洗 logs/ 下所有 .jsonl
#   tools/redact_secrets.sh --check   只检查不修改；发现疑似密钥返回 1
#
# 注意：对话记录是**持续写入**的。清洗后如果继续对话，需要重新跑一遍。
# 同理，若用组委会的工具重新导出日志，也要再清洗一次。
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

while IFS= read -r f; do
    n=$(grep -oE "$PATTERN" "$f" 2>/dev/null | wc -l)
    [ "$n" -eq 0 ] && continue

    total=$((total + n))

    if [ "$mode" = "--check" ]; then
        printf '  %4d 处  %s\n' "$n" "$f"
    else
        sed -i -E "s/${PATTERN}/${PLACEHOLDER}/g" "$f"
        printf '  已清洗 %4d 处  %s\n' "$n" "$f"
    fi
done < <(find logs -type f -name '*.jsonl' 2>/dev/null | sort)

if [ "$mode" = "--check" ]; then
    if [ "$total" -gt 0 ]; then
        echo
        echo "发现 $total 处疑似密钥 —— 提交前请先运行： tools/redact_secrets.sh"
        exit 1
    fi
    echo "logs/ 干净：没有发现疑似密钥"
    exit 0
fi

if [ "$total" -eq 0 ]; then
    echo "logs/ 干净：没有发现疑似密钥，无需修改"
else
    echo
    echo "共清洗 $total 处。如果本会话稍后还会继续，请在最终提交前再跑一次。"
fi
