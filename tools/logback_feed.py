#!/usr/bin/env python3
"""把指定 transcript 喂给官方 contest-log-collector 的 snapshot_core。

跑在**开发虚拟机**里（采集器的工作区闸门要求目录树内有 .repo/，
只有 VM 里的 openvela 工作区满足 —— Windows 侧的独立 clone 不满足）。
等价于 `contest-snapshot --backfill` 的单条路径，但限定在本队会话范围，
不会把 VM 上的无关历史对话顺手采进来。

增量语义：官方 snapshot_core 按 manifest 的 raw_event_count 水位线只导
新增事件，重复执行不产生重复（与手册 Q11 一致）。

用法（由 tools/sync_ai_logs.sh 驱动，也可手动）：
    python3 feed.py [/path/to/transcripts_dir ...]
"""
import json
import os
import pathlib
import subprocess
import sys

CORE = os.path.expanduser(
    "~/openvela_contest/.claude/skills/contest-log-collector/"
    "adapters/shared/snapshot_core.py")
DEST = os.path.expanduser("~/openvela_contest/contest2026_151_mianbao")
# VM 侧本项目的 transcript 目录（Claude Code 把 cwd 摊平成目录名）
PROJ = pathlib.Path(os.path.expanduser(
    "~/.claude/projects/-home-ubuntu-openvela-contest-contest2026-151-mianbao"))
TEAM_ID = "contest2026_151_mianbao"
GITHUB_LOGIN = "xunzhekafei"


def main() -> int:
    # 参数：额外 transcript 目录（Windows 拷来的放 /tmp/logback）
    targets = []
    for arg in sys.argv[1:] or ["/tmp/logback"]:
        targets += sorted(pathlib.Path(arg).glob("*.jsonl"))
    if PROJ.is_dir():
        targets += sorted(PROJ.glob("*.jsonl"))

    env = {**os.environ, "TEAM_ID": TEAM_ID,
           "GITHUB_LOGIN": GITHUB_LOGIN, "CWD": DEST}
    ok = 0
    seen = set()
    for t in targets:
        sid = t.stem
        if sid in seen:
            continue
        seen.add(sid)
        payload = json.dumps({"session_id": sid, "cwd": DEST,
                              "transcript_path": str(t),
                              "hook_event_name": "SessionEnd"})
        r = subprocess.run([sys.executable, CORE, "--tool", "claude-code"],
                           input=payload, text=True, capture_output=True,
                           env=env, cwd=DEST)
        captured = (r.returncode == 0 and "captured" in r.stderr)
        ok += bool(captured)
        tail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
        print("%s  %s  %s" % (sid[:12],
                              "captured" if captured else "rc=%d(skip)" % r.returncode,
                              tail))
    print("captured %d/%d" % (ok, len(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
