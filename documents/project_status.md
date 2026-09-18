# AI模拟面试官 — 项目启动状态总结

> 生成时间：2026-07-09  
> 负责：项目负责人  

---

## 一、已完成的工作

### 1.1 开题报告
- ✅ 技术方案已确定（详见 test-project/详细技术方案与分工.md）
- ✅ 4人分工明确（详见下方分工表）
- ✅ 时间节点已确定：7月9日~9月20日

### 1.2 开发环境
- ✅ openvela_contest 工作区已通过 repo init + repo sync 完成拉取
- ✅ repo 工具已手动安装（绕过 gerrit，使用 GitHub SSH 方式）
- ✅ 专属仓库 contest2026_151_mianbao 已就绪
- ✅ GPIO引脚驱动已在 vendor/allwinnertech 中找到

### 1.3 目录结构

> 下图为 7/9 立项时创建的**骨架**。当前实际目录结构（含 `audio_io.c`、`app_config.h`、`tests/` 等后续新增文件）见根目录 `README.md` 第三节。

已在专属仓库中创建了完整的骨架目录：

```
contest2026_151_mianbao/
├── app/ai_interview/          # 端侧 C 代码
│   ├── main.c                 # 主程序入口（骨架）
│   ├── state_machine.h        # 状态机头文件
│   ├── state_machine.c        # 状态机实现
│   └── network_client.c       # 网络通信模块（骨架）
├── cloud/                     # 云端 Python 服务
│   ├── app.py                 # Flask 主程序
│   ├── asr_service.py         # ASR 服务
│   ├── llm_service.py         # LLM 服务
│   ├── tts_service.py         # TTS 服务
│   └── session_manager.py     # 会话管理
├── skills/                    # Skill Prompt
│   ├── start_interview.json
│   ├── next_question.json
│   ├── evaluate_answer.json
│   ├── generate_feedback.json
│   └── check_timeout.json
├── documents/                 # 文档
│   ├── api_protocol.md
│   └── project_status.md
├── logs/                      # AI Coding 日志
├── .gitignore
└── README.md
```

---

## 二、人员分工与当前状态

> ⚠️ 本节为 **2026-07-09 立项当日** 的状态快照，其中的「未完成」项多数已在后续完成（如音频验证、Wi-Fi、端云联调）。
> **当前完成情况**请看根目录 `README.md` 与 `documents/progress_audit_2026-09-11.md`（工作台账）。
> **9/18 新增**：`question_bank/`（面试题库 2830 题，含可复现导入脚本与题目出处说明）与云端检索模块
> `cloud/question_bank.py` —— 面试官的问题不再由模型现编，改为按岗位与候选人回答取参考题注入提示词，
> 岗位映射不到时静默退化为自由提问。见 `README.md` 4.2.2 与台账 §11.21。

### 分工总览

| 角色 | 成员 | 核心职责 |
|------|------|----------|
| **A同学** | 项目负责人/系统集成工程师 | 硬件平台可用，打通端侧基础数据链路 |
| **B同学** | 端侧逻辑与状态机开发 | 让设备"有逻辑地动起来" |
| **C同学** | 云端能力开发 | 让设备"有智慧" |
| **D同学** | Skill开发与Prompt设计 | 让设备"有灵魂" |

### A同学 — 项目负责人 / 系统集成工程师

| 任务 | 状态 | 下一步动作 |
|------|------|-----------|
| openvela 系统编译与烧录 | ✅ 完成 | - |
| 音频 Codec 驱动验证（录音/播放） | ❌ 未完成 | 在开发板上验证 arecord/aplay |
| Wi-Fi 网络连接与稳定性验证 | ❌ 未完成 | 验证网络连接 |
| 系统联调主导 | ❌ 未开始 | 7月下旬启动 |
| 进度把控与风险管理 | ⏳ 进行中 | 持续 |

### B同学 — 端侧逻辑与状态机开发

| 任务 | 状态 | 下一步动作 |
|------|------|-----------|
| 状态机骨架代码 | ✅ 完成 | - |
| GPIO 按键驱动开发 | ❌ 未完成 | 实现按键输入检测 |
| LED 状态指示驱动开发 | ❌ 未完成 | 实现 LED 控制 |
| 完善状态机逻辑 | ❌ 未完成 | 补充事件处理 |
| 音频采集与上传逻辑实现 | ❌ 未完成 | 实现录音+网络上传 |
| 超时定时器实现 | ❌ 未完成 | 实现超时打断 |
| 与C同学共同定义端云接口格式 | ⏳ 进行中 | 定稿接口文档 |

### C同学 — 云端能力开发

| 任务 | 状态 | 下一步动作 |
|------|------|-----------|
| 云端 Web 服务搭建 (Flask) | ✅ 完成 | - |
| ASR API 对接 | ✅ 完成 | - |
| TTS API 对接 | ✅ 完成 | - |
| LLM API 对接（小米 MIMO） | ✅ 完成 | - |
| 与B同学共同定义端云接口格式 | ⏳ 进行中 | 定稿接口文档 |
| 云端错误处理与容错机制 | ❌ 未完成 | 完善错误处理 |

### D同学 — Skill开发与Prompt设计

| 任务 | 状态 | 下一步动作 |
|------|------|-----------|
| start_interview Skill | ✅ 完成 | - |
| next_question Skill | ✅ 完成 | - |
| check_timeout Skill | ✅ 完成 | - |
| evaluate_answer Skill | ✅ 完成 | - |
| generate_feedback Skill | ✅ 完成 | - |
| System Prompt 迭代优化 | ❌ 未完成 | 收集数据集优化 |
| 演示脚本设计 | ❌ 未开始 | 设计演示用对话 |
| 文档整理 | ❌ 未开始 | 汇总技术文档 |

---

## 三、最近截止日期提醒

| 日期 | 事项 | 负责人 |
|------|------|--------|
| 7月10日 | 提交开题报告 | 全体 |
| 7月11日 | 提交引脚映射表 | A |
| 7月11日 | 获取 xiaomi mimo API 密钥 | C |
| 7月15日 | Skill Prompt 第一版 | D |
| 7月20日 | 接口协议文档定稿 | B, C |
| 7月下旬 | 第一次端云联调 | A, B, C |
| 9月20日 | 作品提交截止 | 全体 |

---

## 四、关键技术选型

| 技术点 | 选型 |
|--------|------|
| 端侧 OS | openvela (dev-ai-contest-2026) |
| 硬件平台 | R528 (r528s3-velaevb1) |
| 云端框架 | Flask（`cloud/app.py`，仅此一个服务） |
| AI 能力 | xiaomi mimo API (ASR + LLM + TTS) |
| 端侧逻辑 | 自研状态机（`app/ai_interview/state_machine.c`）；**未使用** openvela ai_agent 框架 |
| 通信协议 | HTTP + JSON（局域网内明文；见 `documents/api_protocol.md`） |

---

## 五、注意事项

1. 所有4位同学都需要签署 openvela CLA，否则无法提交 PR
2. AI Coding 日志从今天开始记录，每个人每次与AI的交互都要保存
3. 硬件驱动验证（录音/播放/Wi-Fi）要优先完成，否则联调无法进行
4. xiaomi mimo API 密钥要尽早申请，审批可能需要时间

---

## 六、代码验证与硬件烧录指南

> 更新时间：2026-07-13

### 6.1 概述

本章节说明如何将仓库中的代码编译并烧录到全志 R528 开发板上进行验证。我们采用**符号链接**方式，将仓库代码集成到 OpenVela 编译系统中，实现"仓库即源码"的开发模式。

### 6.2 开发环境

| 项目 | 说明 |
|------|------|
| **开发板** | DshanPI openvela Devkit（全志 T113S3 / R528） |
| **操作系统** | OpenVela（基于 Apache NuttX） |
| **编译环境** | `~/vela-opensource/` |
| **仓库目录** | `~/openvela_contest/contest2026_151_mianbao/` |
| **目标配置** | `r528s3-velaevb1` |

### 6.3 目录结构说明

```
~/openvela_contest/contest2026_151_mianbao/   # GitHub 仓库（源码）
├── app/
│   ├── ai_interview/        # 主应用程序
│   └── ai_interview_test/   # ✅ 集成测试程序
├── cloud/                   # 云端服务
├── skills/                  # Skill Prompt
└── documents/               # 文档

~/vela-opensource/            # OpenVela 编译环境
└── apps/examples/
    ├── ai_interview -> 仓库目录/app/ai_interview        # 符号链接
    └── ai_interview_test -> 仓库目录/app/ai_interview_test  # 符号链接
```

### 6.4 编译流程

#### 步骤 1：进入编译目录

```bash
cd ~/vela-opensource/vendor/allwinnertech/lichee
```

#### 步骤 2：激活编译环境

```bash
source vela_env.sh
source envsetup.sh
```

#### 步骤 3：选择目标板

```bash
lunch_nuttx
# 在列表中选择: r528s3-velaevb1
```

#### 步骤 4：配置应用（可选）

```bash
menuconfig
# 导航到: Examples
# 启用: [*] AI Interview Simulator
# 启用: [*] AI Interview Integration Test
```

#### 步骤 5：编译

```bash
m
```

#### 步骤 6：打包

```bash
pack
```

打包完成后，镜像文件位于：
```
~/vela-opensource/vendor/allwinnertech/lichee/out/r528s3/velaevb1_nand/rtos_nuttx_r528s3-velaevb1_uart0_256Mnand.img
```

### 6.5 烧录流程

#### 步骤 1：传输镜像到宿主机

将镜像文件传输到 Windows 宿主机（用于全志烧录工具）：

```bash
# 方式 1：SCP（如果网络配置正确）
scp rtos_nuttx_r528s3-velaevb1_uart0_256Mnand.img user@windows-host:~/

# 方式 2：USB/SD卡拷贝
cp rtos_nuttx_r528s3-velaevb1_uart0_256Mnand.img /media/usb/
```

#### 步骤 2：使用全志烧录工具

1. 打开全志 PhoenixSuit 或 AllWinnertech 烧录工具
2. 选择镜像文件：`rtos_nuttx_r528s3-velaevb1_uart0_256Mnand.img`
3. 连接开发板（USB）
4. 点击"烧录"或"Download"

#### 步骤 3：串口连接

烧录完成后，通过串口连接开发板：

```bash
# Linux/Mac
screen /dev/ttyUSB0 115200

# Windows
# 使用 PuTTY 或 SecureCRT，选择对应 COM 口，波特率 115200
```

### 6.6 测试验证

#### 测试 1：集成测试程序

在 NSH 命令行中运行：

```bash
nsh> ai_interview_test
```

**预期输出：**

```
========================================
  AI模拟面试官 - 集成测试 v1.0
  队伍: mianbao (contest2026_151)
========================================

[TEST 1] 符号链接验证
  ✅ 如果你能看到这条消息，说明符号链接工作正常
  ✅ 代码来自 GitHub 仓库目录

[TEST 2] 构建系统验证
  ✅ Makefile 已正确配置
  ✅ Kconfig 已正确注册
  ✅ 应用已成功编译为 NSH 内置命令

[TEST 3] 硬件平台信息
  📱 目标板: 全志 R528 (T113S3)
  🖥️  开发板: DshanPI openvela Devkit
  📺 屏幕: 3.5寸 LCD

[TEST 4] 功能模块状态
  ✅ 状态机 (state_machine.c) - 已实现
  ✅ 网络通信 (network_client.c) - 已实现（libcurl 上传 / 响应解析）
  ✅ 音频采集与播放 (audio_io.c) - 已实现（DMIC 采集 / aw-alsa 播放）
  ✅ 云端服务 - 已对接（ASR → LLM → TTS，端到端已上板验证）

========================================
  🎉 集成测试完成！
  运行主程序: nsh> ai_interview
========================================
```

#### 测试 2：主程序

```bash
nsh> ai_interview
```

> 主程序即本作品本体，端到端已在开发板上实测通过。交互方式与 LED 状态含义见根目录 `README.md` 4.5 节。

### 6.7 常见问题

#### Q1：编译时找不到新应用？

**解决方案：**
```bash
# 检查符号链接是否正确
ls -la ~/vela-opensource/apps/examples/ai_interview_test/

# 检查 Kconfig 是否注册
grep "ai_interview" ~/vela-opensource/apps/examples/Kconfig
```

#### Q2：烧录后串口无输出？

**解决方案：**
1. 检查串口线连接（TX/RX 是否交叉）
2. 确认波特率设置为 115200
3. 尝试重启开发板

#### Q3：如何更新代码后重新编译？

**流程：**
```bash
# 1. 在仓库目录修改代码
cd ~/openvela_contest/contest2026_151_mianbao/app/ai_interview/
# 编辑代码...

# 2. 重新编译（无需复制，符号链接自动同步）
cd ~/vela-opensource/vendor/allwinnertech/lichee
m

# 3. 重新打包
pack

# 4. 重新烧录
```

### 6.8 验证清单

在最终演示前，请确认以下项目：

| 验证项 | 状态 | 说明 |
|--------|------|------|
| ☐ 编译成功 | | `m` 命令无错误 |
| ☐ 打包成功 | | 生成 `.img` 文件 |
| ☐ 烧录成功 | | 开发板启动正常 |
| ☐ 串口可连接 | | 能进入 NSH 命令行 |
| ☐ 测试程序运行 | | `ai_interview_test` 输出正确 |
| ☐ 主程序运行 | | `ai_interview` 能启动 |
| ☐ 网络连接 | | 开发板能访问云端服务 |
| ☐ 音频功能 | | 录音/播放正常工作 |

---

## 七、云端服务现状

> 更新时间：2026-09-14

### 7.1 概述

云端是一套 **Flask HTTP 服务**（`cloud/app.py`，监听 `0.0.0.0:5000`），为开发板提供 ASR / LLM / TTS 能力。**作品的主交互在开发板上** —— 按键启动、LED 指示、语音问答；云端不提供浏览器界面。

### 7.2 接口

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/health` | GET | 健康检查（端侧启动时自检） |
| `/api/interview` | POST | **主链路**：上传 base64 WAV（`state=recording_finished`）→ 返回识别文本、回复文本与 base64 音频 |
| `/api/test/asr` | POST | ASR 单项测试 |
| `/api/test/tts` | POST | TTS 单项测试 |

请求/响应字段见 `documents/api_protocol.md`。

### 7.3 辅助脚本

| 脚本 | 用途 |
|------|------|
| `test_services.py` | ASR / TTS / TTS→ASR 集成测试 |
| `play_tts.py` | 在电脑上播放 TTS 合成结果 |
| `demo_interview.py` | 不接开发板，直接在电脑上跑一轮面试流程 |

### 7.4 启动方式

```bash
cd cloud
pip install -r requirements.txt
export MIMO_API_KEY="<小米 MIMO API key>"   # 只放环境变量，不入仓库
python3 app.py                              # 监听 0.0.0.0:5000
```

启动时会打印 `API Key: sk-xxxxxxxxxx...`（前 10 位）；没有这一行就是没读到 key。

### 7.5 关于浏览器界面（2026-09-14 更正）

本文档 2026-07-14 之前的版本在此处记为「已完成 Web 管理界面」，并列出 `cloud/templates/index.html`、`cloud/WEB_INTERFACE.md`、`cloud/start_web.sh`、`cloud/test_web.py` 四个文件 —— **这四个文件从未进入过本仓库的 git 历史，本仓库也从未提供过浏览器界面**。

实际情况：2026-07-13 至 07-14 曾在**开发期工作区**（仓库外的 `test-project/web_frontend/`）搭过一版浏览器文字面试界面原型（同名的 4 个文件在那里），其 Flask 后端未落地、现已不存在。该原型**未纳入本仓库，也不是本作品的功能**。此处留档更正，以免文档与仓库实际内容不符。

---

## 八、时间线更新

> 更新时间：2026-07-13（下表为当日的计划快照；截至 2026-09-14 的实际完成情况见 `README.md` 与 `documents/progress_audit_2026-09-11.md`）

| 阶段 | 时间 | 任务 | 状态 |
|------|------|------|------|
| **环境搭建** | 7月9日-7月12日 | 开发环境配置、API 集成、日志工具 | ✅ 完成 |
| **代码验证** | 7月13日 | 硬件烧录、集成测试 | ✅ 完成 |
| **Web界面原型** | 7月13日 | 浏览器文字面试界面原型（在开发期工作区，**未纳入本仓库**） | ⚠️ 原型 |
| **正式开发** | 7月16日-7月20日 | 完善端侧功能、云端 API、音频集成 | ⏳ 待开始 |
| **端云联调** | 7月21日-7月25日 | 完整功能测试、语音+文字面试 | ⏳ 待开始 |
| **优化完善** | 7月26日-8月 | 性能优化、Prompt 调优、UI 美化 | ⏳ 待开始 |
| **最终演示** | 9月20日前 | 提交作品 | ⏳ 待开始 |

### 7月13日完成的工作

1. ✅ **硬件烧录验证**
   - 成功将代码编译并烧录到 R528 开发板
   - 验证了符号链接集成方式
   - 测试程序 `ai_interview_test` 运行正常

2. ⚠️ **浏览器界面原型**（*2026-09-14 更正*）
   - 当日在**开发期工作区**（仓库外的 `test-project/web_frontend/`）搭过一版浏览器文字面试界面原型
   - 它**未纳入本仓库**，其 Flask 后端未落地、现已不存在，**不构成本作品的功能**
   - 本作品的主交互是开发板上的按键 + 语音问答（见第七节）

3. ✅ **项目文档更新**
   - 更新了 `project_status.md` 文档
   - 记录了硬件烧录流程
