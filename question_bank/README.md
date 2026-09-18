# 面试题库（AI 侧）

本目录是「AI 模拟面试官」云端选题用的**离线题库**，vendored 自同一作者的开源项目
[`xunzhekafei/myagent`](https://github.com/xunzhekafei/myagent)（MIT），配合
[`../skills/README.md`](../skills/README.md) §5.1 那条「面试问题库｜每岗位 50+ 题」的
数据需求 —— 在本仓库里就是这份数据。

**题只含题干，不含答案**（三个来源都如此，是有意保留的：模拟面试给候选人看到答案就失去意义了）。
云端只把题干当作**选题方向**注入提示词，不照读、不逐字念 —— 见
[`../cloud/question_bank.py`](../cloud/question_bank.py) 与 `../documents/progress_audit_2026-09-11.md` §11.21。

## 目录

```
question_bank/
├── README.md          ← 本文件（出处表 = 英文题库的**唯一**出处凭证，见下）
├── LICENSE            ← MIT（Copyright (c) 2026 xunzhekafei）
├── data/
│   ├── zh_questions.json   1183 道中文 AI 岗题（341,777 B）
│   └── ai_questions.json   1647 道英文 AI 岗题（1,440,845 B）
└── import/            ← 导入脚本，可完整复现上面两份数据
    ├── import_dataset.py      从 HuggingFace 数据集导入英文题
    └── import_github_bank.py  从 8 个 GitHub 仓库导入中文（含前端）题
```

## 数据文件与出处

两份文件的 sha256（与上游 `myagent` **逐字节一致**，未做任何清洗、裁剪或改写）：

| 文件 | 条数 | 大小 | sha256 |
| ---- | ---- | ---- | ------ |
| `zh_questions.json` | 1183 | 341,777 B | `32aa229889f0fdef5a5f9639d5f41aa15b5a8c57c0972cedd8c1eeb4a20d5482` |
| `ai_questions.json` | 1647 | 1,440,845 B | `2fbc293920ac019a19d6061ca450b3b53ff623d1d062712e64dc9d358920abb1` |

### `zh_questions.json` — 1183 道，全部中文

每条记录自带 `source` 字段（原样保留，可逐条核对），下表是汇总：

| 来源仓库 | 条数 | 岗位 | 许可 |
| ---- | ---- | ---- | ---- |
| [`guocong-bincai/ai-interview-guide`](https://github.com/guocong-bincai/ai-interview-guide) | 640 | AI 应用开发 | MIT |
| [`lengyue1024/BAT_interviews`](https://github.com/lengyue1024/BAT_interviews) | 208 | 大模型算法工程师 / AI 应用开发 | MIT |
| [`bcefghj/ai-agent-interview-guide`](https://github.com/bcefghj/ai-agent-interview-guide) | 181 | AI Agent 开发 | MIT |
| [`bcefghj/learn-nanobot`](https://github.com/bcefghj/learn-nanobot) | 134 | AI Agent 开发 | MIT |
| [`aceliuchanghong/FAQ_Of_LLM_Interview`](https://github.com/aceliuchanghong/FAQ_Of_LLM_Interview) | 20 | 大模型算法工程师 | MIT |

岗位分布：**AI 应用开发 748 / AI Agent 开发 315 / 大模型算法工程师 120**。
抽取时只取题目、不复制答案；各来源的目录白名单与排除规则（求职向目录、个人面经、
简历模板等）写在 `import/import_github_bank.py` 的 `SOURCES` 里，逐条可查。

### `ai_questions.json` — 1647 道，全部英文

| 来源 | 条数 | 岗位 | 许可 |
| ---- | ---- | ---- | ---- |
| [HuggingFace `Davichick/InterviewForge_GenDS`](https://huggingface.co/datasets/Davichick/InterviewForge_GenDS)（`interview_forge_v3_complete.csv`） | 1647 | AI/ML Engineer 576 / Data Scientist 495 / Data Analyst 576 | MIT |

> ⚠️ **这份数据集没有 per-record 的来源字段**，上表因此是本仓能提供的**唯一**出处凭证 ——
> 删掉它就无法回溯这 1647 道题的来源了。原始 CSV 的拉取命令见 `import/import_dataset.py`。

## 字段说明

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `question` | str | 题干（**唯一必填**，其余字段都可能为空） |
| `keywords` | list[str] | 检索关键词。**英文题库 1647/1647 有值；中文题库 1183 条全为空数组** |
| `role` | str | 岗位。取值见上两节；**中文题库的岗位名带空格**（`AI 应用开发`） |
| `category` | str | 考点分类（如 `RAG 系统面试题`、`System Design & Architecture`），子串匹配 |
| `level` | str | 难度。**只有英文题库有值**（`Level 1/2/3`）；中文题库全为空 |
| `stage` | str | 面试阶段。英文题库四档全覆盖；中文题库仅 10 条有值（行为面） |
| `lang` | str | `"zh"`。**只有中文题库有该字段** |
| `source` | str | 来源仓库。**只有中文题库有该字段** |
| `url` | str | 原始 issue 链接。本仓**两份数据里都没有**（随前端题库一起留下，见下） |

## 许可

- 本目录的**导入脚本与文档**：MIT，见 [`LICENSE`](LICENSE)。
- **两份题库数据**：MIT。中文各源的 `source` 字段与上表逐条对应；英文来源为上述
  HuggingFace 数据集（MIT）。使用/再分发时请保留本文件的出处表。

## 复现导入

两个脚本都在**仓库根目录**下运行，产物写回 `question_bank/data/`：

```bash
# 英文题（先拉原始 CSV，huggingface.co 直连不通时用 hf-mirror 镜像）
curl -L -o /tmp/interview_forge.csv \
  https://hf-mirror.com/datasets/Davichick/InterviewForge_GenDS/resolve/main/interview_forge_v3_complete.csv
python3 question_bank/import/import_dataset.py /tmp/interview_forge.csv

# 中文题（浅克隆 8 个仓库到临时目录后导入；加 --fresh 忽略已有克隆）
python3 question_bank/import/import_github_bank.py
```

⚠️ 导入依赖 GitHub / HuggingFace 的网络连通性，且会**覆盖** `data/` 下的同名文件。
重新导入后建议核对 sha256 是否仍与上表一致（上游仓库更新会导致题目变化）。
**离线校验题库本身不需要网络** —— 见 `../cloud/test_question_bank.py`。

## 与上游的 3 处差异

数据本身**逐字节一致**（sha256 见上表），差异只在布局与收录范围：

1. **目录布局**：上游是 `interview/data/` + `interview/import_*.py`，本仓收进
   `question_bank/`（`data/` 与 `import/` 分开，与 `skills/` 同级的顶层目录，便于评委浏览）。
   两个导入脚本的 `DATA_DIR` / `OUT_PATH` 相应由 `parent/"data"` 改为 `parent.parent/"data"`。
2. **收录范围**：上游三份共 8990 题，本仓**只收 AI 侧两份**，前端 `fe_questions.json`
   （6160 题）不随仓分发 —— 理由见下节。导入脚本保留前端来源，导入过程仍可完整复现。
3. **加载方式**：上游检索层用 `glob("*.json")` 扫整个目录，本仓 `cloud/question_bank.py`
   改用 `BANK_FILES` **白名单**。这处差异是**有意的防御**：上面第 2 条意味着
   `data/` 下随时可能多出 `fe_questions.json`，白名单能让它**静默不进题库**，
   而 glob 会把它混进来（6000 多道前端题会淹没 AI 题）。

## 已知局限

- **英文题干极长**：1647/1647 条都超过 60 字（中位数 508 字，最长 1068 字，多为多部分场景题）。
  注入提示词时会截断到 60 字，**只能当选题方向用，绝不能照读** —— 云端提示词里显式要求
  英文资料先译成中文再改写提问。演示岗位（AI 应用开发）走的是中文题库，不受影响。
- **中文题库无 `keywords`、无 `level`**：检索只能拿题干打分，难度只能靠提问方式控制
  （追问「为什么」「边界在哪」就是加难）。
- **题干口语化程度不一**：`FAQ_Of_LLM_Interview` 是笔记型仓库，题目由文件名生成，
  形如「请讲讲「X」的关键点，并结合实际场景举例。」—— 这类题更适合当话题引入。
- **不含答案**：有意为之。
- **题库岗位名带空格**（`AI 应用开发`）：在 NSH 里用 `set ROLE ...` 传参会**被空格切碎**
  （值只剩 `AI`），导致静默退化成自由提问。板子侧默认值改在 Kconfig 里，不走 `set`；
  详见 `../README.md` §4.7。

## 为什么只有 AI 侧两份

本队参赛作品是 **AI 岗**模拟面试官（演示岗位 `AI 应用开发`），前端题库（6160 题，
1.8 MB）在本作品里**用不到**：它会让题库体积翻倍、把 `role` 映射表撑大一倍，而检索层
每次只会挑 3 条题干。留脚本、不留数据，是需要时能一条命令找回来的最小代价。
