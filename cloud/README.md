# AI模拟面试官 — 云端服务

> 负责：A同学  
> 创建：2026-07-12 · 最近更新：2026-09-29（第二节目录结构、新增 3.7 会话落盘与报告导出、5.5 校验脚本补 `run_tests.sh`）

---

## 一、项目简介

本目录包含 AI 模拟面试官的**云端服务**，基于 Flask 框架构建，集成小米 MIMO API 提供 ASR（语音识别）和 TTS（语音合成）能力。

---

## 二、目录结构

```
cloud/
├── app.py                  # Flask 主程序（云端 API 入口）
├── asr_service.py          # ASR 语音识别服务
├── tts_service.py          # TTS 语音合成服务
├── llm_service.py          # LLM 大语言模型服务（注入题库参考块）
├── session_manager.py      # 会话管理模块
├── question_bank.py        # 题库检索模块（纯标准库，见 3.5）
├── reply_guard.py          # 回复闸门：剥掉「判断：/理由：」这类元叙述（见 3.6）
├── finish_guard.py         # 结束判据：候选人明说「结束吧」才提前收尾（见 3.7）
├── score_guard.py          # 评分 JSON 校验（结构化评分用，纯函数）
├── session_store.py        # 会话落盘：原子写、永不抛异常（见 3.7）
├── report_export.py        # 报告导出：Markdown / JSON 渲染（见 3.7）
├── requirements.txt        # Python 依赖列表
│
├── static/index.html       # 对话展示页 + 报告卡片（只读，见 ../README.md 4.2.1）
├── data/sessions/          # 运行期落盘的会话 json（.gitignore，删掉不影响运行）
│
├── test_services.py        # ASR/TTS 服务测试脚本（运行后在 cloud/ 下生成下面两个 wav）
├── play_tts.py             # TTS 语音播放工具
├── demo_interview.py       # 面试流程演示脚本
│
├── test_question_bank.py   # 校验①②③ 各模块单元测试（纯标准库，不花钱、不联网）
├── test_reply_guard.py
├── test_finish_guard.py
├── test_score_guard.py
├── test_session_store.py
├── test_report_export.py
├── run_tests.sh            # 顺序跑上面全部单元测试（本地与 CI 共用；跳过 test_services.py）
├── rehearsal.py            # 校验④  PC 端 11 轮全流程试运行（真打 ASR/LLM/TTS）
├── ab_next_question.py     # 校验⑤  提示词改版的单变量 A/B（真打 LLM）
│
└── README.md               # 本文件
```

> `test_services.py` 运行后会生成 `test_tts_output.wav`（非流式）与 `test_tts_stream_output.wav`（流式），
> 各约 300KB。它们是**测试产物、不入仓库**（已在 `.gitignore` 中），复跑一次脚本即可重新生成。

---

## 三、已实现功能

### 3.1 ASR 语音识别 (`asr_service.py`)

- ✅ 小米 MIMO ASR API 集成
- ✅ 支持 WAV/MP3 音频格式
- ✅ 支持中文/英文/自动语言检测
- ✅ 支持 base64 和文件两种输入方式

**主要函数：**
```python
asr_audio_to_text(audio_base64, audio_format, language)  # base64 输入
asr_audio_file_to_text(file_path, language)              # 文件输入
```

### 3.2 TTS 语音合成 (`tts_service.py`)

- ✅ 小米 MIMO TTS API 集成
- ✅ 预置音色：冰糖（中文女性音色，适合面试官场景）
- ✅ 支持非流式和流式两种合成模式
- ✅ 支持自然语言风格控制

**主要函数：**
```python
tts_text_to_audio(text, voice, style)                    # 非流式合成，返回 base64
tts_text_to_audio_stream(text, output_file, voice, style)  # 流式合成，保存到文件
```

### 3.3 LLM 服务 (`llm_service.py`)

- ✅ 小米 MIMO LLM 接入，多轮上下文面试问答
- ✅ 按 `skills/*.json` 加载人设与提示词（`start_interview` / `next_question` / `evaluate_answer` / `generate_feedback`）
- ✅ 每轮按**岗位 + 候选人最近一句回答**从题库取 3 道参考题，注入 `next_question` 的 system prompt（岗位对不上则不加，见 3.5）
- ✅ 思考关闭（`thinking={"type":"disabled"}`）：`mimo-v2.5` 是推理模型，reasoning 与正文**共用** `max_tokens`，不关会让正文被截断
- ✅ 返回 `next_action`（`continue` 继续提问 / `finish` 出报告）供端侧状态机判断

**主要函数：**
```python
start_interview(role)                     # 开场提问
next_question(role, history, last_answer) # 追问
evaluate_answer(role, question, answer)   # 单题点评
generate_feedback(role, history)          # 总结报告
```

### 3.4 会话管理 (`session_manager.py`)

- ✅ 会话创建 / 复用、user 与 assistant 消息入历史、超时会话清理（默认 3600s）
- ✅ 上下文由 `get_history()` 提供给 LLM，实现多轮追问
- ✅ `snapshot()`：导出可直接 `jsonify` 的纯数据（落盘与网页展示都走它，见 3.7）。**只读，且刻意不往 `history` 的字典里加字段** —— 那份 history 会被原样送进 LLM 的 `messages` 参数
- ✅ `finish()`：标记"这场结束了"。此前零调用者、`is_finished` 恒为 `False`，网页因此无从判断该不该渲染报告卡片（见 3.7）

### 3.5 题库检索 (`question_bank.py`)

- ✅ 启动预热 + 缓存（双重检查锁）：`warmup()` 返回题数与岗位名，供 `app.py` 打启动日志
- ✅ 岗位归一化与别名：NFKC + 去空白/引号 + 转小写 → 精确命中 → 别名表 → 双向包含取最长；`产品经理` 这类对不上的岗位 `normalize_role()` 返回 `""`、**拼出空块而不报错**
- ✅ 选题：关键词检索优先，未命中按类别轮换（类别顺序带固定优先级，保证 10 轮内问到编码/基础原理类）
- ✅ 拼装参考块（≤400 字，无 Markdown），供 `next_question` 注入 system prompt
- ✅ **只用标准库**，且无 `random`、无 `glob`：同一输入结果完全可复现 —— 这两条由单测里的 AST 检查守住

**主要函数：**
```python
warmup()                                       # 预热，返回 {loaded, records, roles, dir}
bank_roles()                                   # 题库里的岗位名列表
normalize_role(role)                           # 岗位名 → 题库岗位（对不上返回 ""）
search_questions(query, role, category, level, stage, limit)
pick_candidates(role, query, asked_text, round_index, limit=3)
build_reference_block(role, query, asked_text, round_index, limit)  # 无匹配返回 ""
```

**数据**：`../question_bank/data/`（2830 题 / 6 个岗位 / 2 个 JSON）。文件名是**白名单**，不用 `glob` —— 目录里多放一个 `fe_questions.json` 也不会被读进来。

> 五条设计约束（为什么这么写、参考块为什么只能进 system prompt）都记在模块 docstring 里；对应的 22 项单测见 5.5。

### 3.6 回复闸门 (`reply_guard.py`)

- ✅ `strip_meta()`：把模型回复里的「判断：/理由：/---/Markdown 表格」这类**元叙述**剥掉，只留下要对候选人说的话
- ✅ `clean_history()`：**读进来的历史也过一遍** —— 已经脏掉的会话能自愈（§11.20 那个故障不会自己好，这是唯一不靠重启的恢复手段）
- ✅ 干净文本零改动（只有检测到元叙述痕迹才动手）、幂等、确定性、只用标准库
- ✅ 用在 `llm_service.next_question()` 的**出口与入口**两处；剥空了用兜底问句顶上

**为什么要在代码里补这一道**（台账 §11.20 / §11.21）：`next_question` 是语音链路，模型的每个字都会被 TTS 逐字念出来。提示词层面已经禁过一轮，但 9/18 的 A/B 证明**光靠提示词挡不住被污染的历史** —— 删掉提示词里的「错误示例」之后，模型改从历史里学那个格式，P 组 30 次里仍有 4 次输出 `判断：追问细节 … 理由：…`（169~229 字）。提示词是"劝"，闸门是"拦"。

> 它**只用于问题链路**：报告走的是 `generate_feedback`，`strip_meta()` 会砍掉报告里的非问句段落，绝不能套用。

### 3.7 会话落盘、语音结束、报告导出（2026-09 新增）

大赛提交之后转入长期迭代做的第一批：**板子上的固件一行没改**，全部是云端增强，旧固件照样能用（响应体只增字段、只增值，`"continue"` / `"finish"` 两个值保持不变 —— 端侧 `next_action` 是 16 字节定长，且只在 `strcmp(next_action,"continue") != 0` 时清会话）。

| 能力 | 文件 | 说明 |
|---|---|---|
| **会话落盘** | `session_store.py` | 每轮结束写一份 `data/sessions/<sid>.json`。原子写（临时文件 + `os.replace`），**`save()` 永不抛异常** —— 落盘失败只是少一份存档，绝不能把一次成功的面试变成 500。写盘位置在 TTS 之后，不拖慢板子正在等的那个回包 |
| **重启存活** | `app.py` 的 `_snapshot()` | 取快照时**内存优先、磁盘兜底**，所以 `/api/history` 和 `/api/export` 在 Flask 重启后仍能取到上一场 |
| **语音结束** | `finish_guard.py` | 候选人说「结束吧 / 谢谢老师，我没有其他问题了」时提前出报告。四道闸：归一化 → ≤20 字 → 无问号 → 剥掉首尾客套后核心命中白名单。**宁可漏判不可误判**：「没问题」「可以了」「就这样吧」故意不在白名单里（技术回答里太常见） |
| **报告导出** | `report_export.py` + `GET /api/export/<sid>?format=md\|json` | Markdown 给人读、JSON 给以后做纵向分析。**文件名纯 ASCII**（中文标题写在正文里），避开 `Content-Disposition` 的非 ASCII 编码坑 |

**顺带修掉的两个静默不一致**（都是"文档写死、实现却不是"）：

1. **静音轮不再推迟报告**。空识别短路那句「抱歉，我没听清」原先会被 `add_ai_message` 写进历史，而它没有对应的 user 消息 → 历史变奇数 → 报告判据 `len(history) - 1 >= 20` 被推迟一次。现在它照常返回、照常有声，只是**不留痕**。回归判据在 `rehearsal.py --no-tts`：连打 3 轮静音后历史必须是 **0 条**。
2. **`is_finished` 变真**。`session_manager.finish()` 此前零调用者，于是"这场结束了没有"在云端根本不存在，网页无从决定该不该渲染报告卡片。现在 `next_action != "continue"` 时调用它，判据与响应体里的 `type` 完全一致。

> ⚠️ **`session_id` 现在是文件名**，所以 `session_store` 只接受 `^[A-Za-z0-9_-]{1,64}$`；不合规的 id 一律拒绝写入与读取（`../../etc/passwd` 这类在路由层就返回 404）。

---

## 四、环境配置

### 4.1 Python 依赖

```bash
pip install -r requirements.txt
```

依赖列表：
- Flask 2.3.3
- requests 2.31.0
- openai >= 1.0.0
- numpy >= 1.24.0
- soundfile >= 0.12.0

### 4.2 API 配置

使用环境变量配置小米 MIMO API Key（**Key 只走环境变量，不入仓库、不进日志**；`llm_service.py` 的 `if __name__ == "__main__"` 自检也只报"已配置/未配置"，不打 key 内容，连前缀都不打）：

```bash
export MIMO_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

**代码中的读取方式：**
```python
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
```

---

## 五、使用方法

### 5.1 测试 ASR/TTS 服务

```bash
cd /home/ubuntu/openvela_contest/contest2026_151_mianbao/cloud
python3 test_services.py
```

测试内容：
- TTS 非流式合成
- TTS 流式合成
- ASR 文件识别
- ASR base64 识别
- TTS → ASR 集成测试

### 5.2 播放 TTS 语音

```bash
# 使用默认文本
python3 play_tts.py

# 使用自定义文本
python3 play_tts.py "你好，欢迎参加面试"
```

### 5.3 面试流程演示

```bash
# 简单演示（只播放问题）
python3 demo_interview.py

# 完整演示（播放 + 录音 + 识别）
python3 demo_interview.py --full
```

### 5.4 启动 Flask 服务

```bash
export MIMO_API_KEY="<小米 MIMO API key>"   # 只放环境变量，不入仓库；忘设则 TTS 静默返回空音频
python3 app.py                              # 监听 0.0.0.0:5000
```

**判断 key 有没有读到，不要看启动日志** —— `app.py` **不会打印任何 key 信息**，`/api/health` 也不校验 key、永远返回 ok。**请打一发 TTS**：

```bash
curl -s -X POST http://127.0.0.1:5000/api/test/tts \
  -H 'Content-Type: application/json' -d '{"text":"自检"}' \
  | python3 -c "import sys,json; a=json.load(sys.stdin).get('audio',''); print('key OK, '+str(len(a))+' 字符 base64' if a else '⚠️ audio 为空 —— key 没读到')"
```

启动日志里另有一行是**必须确认**的：`[题库] 就绪：2830 道题，岗位：…`。**少了这句说明题库没加载** —— 面试照常能跑，只是不再注入参考题（静默退化，见 `../README.md` 4.8 关卡 6）。

端侧（开发板）通过 `POST /api/interview` 调用，接口说明见 `../documents/api_protocol.md`。

---

### 5.5 校验脚本（改提示词 / 改题库之后怎么验）

改动 `skills/*.json`、`question_bank.py` 的选题逻辑，或 `question_bank/data/` 之后，按这个顺序验：

| # | 脚本 | 验什么 | 跑法 | 通过标准 | 花钱 |
|---|------|--------|------|----------|------|
| ① | `bash run_tests.sh` | 全部模块的单元测试（题库 / 回复闸门 / 结束判据 / 评分校验 / 落盘 / 导出） | `bash run_tests.sh` | 每个文件全过（脚本会汇总"✅ N 个测试文件全部通过"） | 否 |
| ② | `test_*.py` | 单独跑某一个（改哪个模块跑哪个） | `python3 test_finish_guard.py` | 全过 | 否 |
| ③ | `rehearsal.py` | PC 端整条链路 11 轮：ASR→LLM→TTS 全真调，逐轮体检 | **先起 Flask**，再 `python3 rehearsal.py` | 11 轮全 HTTP 200、`next_action`/`type` 逐轮对得上、第 11 轮出报告、历史 22 条、问句 ≤150 字、TTS ≤4 MiB、无参考块泄漏、**无兜底文案**、导出接口 200 | 是 |
| ③b | `rehearsal.py --say-finish --rounds 3` | 语音结束那条路径（真过一遍 TTS→ASR，看转写还能不能命中白名单） | 同上 | 第 3 轮 `type=report`、`next_action=finish`、导出可用 | 是 |
| ③c | `rehearsal.py --no-tts` | 静音自检：空识别短路 + **历史奇偶性** | 同上 | 3 轮静音后历史 **0 条**、每轮都有短回复与音频 | 是 |
| ④ | `ab_next_question.py` | 提示词改版的效果对照（旧版 vs 新版，**单变量**） | 先 `--dry-run` 人工审参考块，再 `--n 30` | 空返回 ≤1/30、平均字数 ≤ 旧版×1.2、Markdown 与编号残留 0、≥90% 以问号结尾；报告 ≤250 字且 ≥90% 含「」原话引用 | 是 |

常用参数：`rehearsal.py --role "AI/ML Engineer"` 换岗位（走英文题库）、`--rounds 3` 只跑 3 轮；`ab_next_question.py --n 2` 冒烟、`--group P` 只跑一组、`--dry-run` 完全不花钱。

> ①② 是纯本地的（**不需要 API key**），改完随手就能跑；③④ 会真打 API，通常只在**改提示词/改闸门/改选题逻辑**之后跑。④ 的 `--group` 支持只重测失败的那一臂（P 提示词 / B 题库 / R 报告）。
>
> `run_tests.sh` 会**跳过 `test_services.py`** —— 那是个真调 API、会生成 wav 的集成脚本，不是单元测试，混进 CI 会又花钱又不稳。
>
> **判据补强的两条经验**（2026-09）：`rehearsal.py` 原先只查"不该出现的痕迹"（泄漏串），于是**全链路失败时它依然是绿的** —— 模型调不通 → 各处 return 兜底串 → HTTP 200、结构完整、没有泄漏串，全部判据通过。现在它专门查一类 `FALLBACK_STRINGS`（"生成报告失败"等），**兜底文案出现就算不合格**。另一条：判据要跟着判据本身变 —— 报告轮现在由结束判据决定，"末轮必是报告"只在 `--rounds 11` 或 `--say-finish` 时成立，写死会变成假失败。

> **11 轮是怎么来的**：端侧只发 `state="recording_finished"`（`start_interview` 在真实链路上不可达），结束判据是历史凑满 `HISTORY_FINISH_THRESHOLD = 20` 条，第 N 次调用时历史有 `2N-1` 条 —— 所以报告轮落在**第 11 次**调用，不是第 10 次。轮数对不上先看脚本 docstring 顶部那三条坑。
>
> 三个脚本的判据都写成文件顶部的 `MAX_*` / `MIN_*` 常量，**改阈值要同步更新台账 §11.21**。

---

## 六、技术说明

### 6.1 API 调用方式

使用 OpenAI 兼容的客户端调用小米 MIMO API：

```python
from openai import OpenAI

client = OpenAI(
    api_key=MIMO_API_KEY,
    base_url="https://api.xiaomimimo.com/v1"
)
```

### 6.2 音频格式

- **ASR 输入**：WAV 或 MP3，base64 编码
- **TTS 输出**：WAV 格式，24kHz 采样率

### 6.3 服务器音频工具

- **播放**：`paplay`（PulseAudio）或 `aplay`（ALSA）
- **录音**：`arecord`（ALSA），16kHz，16-bit，单声道

---

## 七、测试结果（2026-07-12）

| 测试项 | 状态 | 说明 |
|--------|------|------|
| TTS 非流式合成 | ✅ 通过 | 生成 299KB WAV 音频 |
| TTS 流式合成 | ✅ 通过 | 生成 314KB WAV 音频 |
| ASR 文件识别 | ✅ 通过 | 识别准确率 100% |
| ASR base64 识别 | ✅ 通过 | 识别准确率 100% |
| TTS → ASR 集成 | ✅ 通过 | 原文与识别结果完全匹配 |
| 语音播放 | ✅ 通过 | PulseAudio 播放正常 |
| 语音录音 | ✅ 通过 | ALSA 录音正常 |

---

## 八、开发计划完成情况

> 2026-09-14 更新：原「下一步计划」各项均已完成。接口路径以实际实现为准（与当时设想的 `/asr`、`/tts`、`/interview` 略有出入）。

| 计划项 | 实际实现 | 状态 |
|--------|----------|------|
| 完善 Flask API (`app.py`) | `/api/interview`（主链路）、`/api/health`、`/api/test/asr`、`/api/test/tts` | ✅ |
| 集成 LLM 服务 (`llm_service.py`) | 对接小米 MIMO LLM，多轮上下文问答 + `next_action` 控制 | ✅ |
| 完善会话管理 (`session_manager.py`) | 会话复用、对话历史、超时清理 | ✅ |
| 端云联调 | 录音 → ASR → LLM → TTS → 端侧播放，**已在开发板上端到端验证**（2026-09-13） | ✅ |

---

## 九、负责人

- **A同学**：云端服务器开发、ASR/TTS 集成

---

## 十、相关文档

- [项目状态文档](../documents/project_status.md)
- [API 协议文档](../documents/api_protocol.md)
- [小米 MIMO ASR 文档](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition)
- [小米 MIMO TTS 文档](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Text-to-Speech)
