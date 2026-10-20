#!/bin/bash
# AI Coding 会话日志增量归集（Git Bash 里跑）。
#
# 背景：官方采集器有"工作区闸门"（目录树内须有 .repo/），Windows 这份独立
# clone 不满足 —— 所以增量归集经开发 VM（192.168.93.141，openvela 工作区在
# 那边）中转：把本机 transcript 拷过去过官方 snapshot_core，再把 logs/ 拉回来。
#
# token 记录：官方采集器在每条事件里自动写 model / tokens_in / tokens_out，
# 无需额外操作。增量语义：水位线去重，重复跑不会重复导。
#
# 用法：bash tools/sync_ai_logs.sh        （跑完 git add logs/ 提交即可）
# 前置：VM 在跑（vmrun list 可见）、ssh 192.168.93.141 免密可用。
set -e

VM=192.168.93.141
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TRANSCRIPTS="$USERPROFILE/.claude/projects/d------contest2026-151-mianbao"

echo "== 1/3 上传本机 transcript 到 VM =="
ssh "$VM" "mkdir -p /tmp/logback"
scp "$TRANSCRIPTS"/*.jsonl "$VM":/tmp/logback/
scp "$REPO/tools/logback_feed.py" "$VM":/tmp/logback/feed.py

echo "== 2/3 VM 侧跑官方采集器（增量） =="
ssh "$VM" "python3 /tmp/logback/feed.py"

echo "== 3/3 拉回 logs/ =="
scp -r "$VM":/home/ubuntu/openvela_contest/contest2026_151_mianbao/logs "$REPO/"

echo "完成。提交： git add logs/ && git commit -m 'logs: sync AI sessions' && git push"
