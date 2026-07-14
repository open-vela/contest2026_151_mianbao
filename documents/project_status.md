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
| 云端框架 | Flask / FastAPI |
| AI 能力 | xiaomi mimo API (ASR + LLM + TTS) |
| AI Agent | openvela ai_agent 框架 |
| 通信协议 | HTTPS + JSON |

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
  ⏳ 网络通信 (network_client.c) - 待实现
  ⏳ 音频采集 - 待集成
  ⏳ 云端服务 - 待对接

========================================
  🎉 集成测试完成！
  下一步: 实现完整的 AI 面试功能
========================================
```

#### 测试 2：主程序（待完善）

```bash
nsh> ai_interview
```

> ⚠️ 主程序当前为骨架代码，功能待完善。

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

## 七、Web 管理界面

> 更新时间：2026-07-13

### 7.1 概述

为了更直观地展示面试内容和评价报告，我们开发了一个 **Web 管理界面**。该界面运行在电脑浏览器上，通过网络访问云端服务，提供文字形式的面试交互体验。

### 7.2 功能特性

| 功能 | 说明 | 状态 |
|------|------|------|
| **面试控制** | 选择岗位（6种）、选择风格（4种） | ✅ 已完成 |
| **实时对话** | 文字形式显示面试问答过程 | ✅ 已完成 |
| **评价报告** | 综合评分、各维度评分、详细评价 | ✅ 已完成 |
| **历史记录** | 查看过往面试记录 | ✅ 已完成 |
| **响应式设计** | 支持桌面和移动端访问 | ✅ 已完成 |

### 7.3 文件结构

```
cloud/
├── templates/
│   └── index.html          # Web 界面主页面
├── WEB_INTERFACE.md        # 详细使用说明
├── start_web.sh            # 一键启动脚本
└── test_web.py             # 测试验证脚本
```

### 7.4 启动方式

#### 方式 1：使用启动脚本（推荐）

```bash
# 1. 设置 API Key
export MIMO_API_KEY="sk-你的API密钥"

# 2. 启动服务
cd /home/ubuntu/openvela_contest/contest2026_151_mianbao/cloud
./start_web.sh
```

#### 方式 2：手动启动

```bash
cd /home/ubuntu/openvela_contest/contest2026_151_mianbao/cloud
export MIMO_API_KEY="sk-你的API密钥"
python3 app.py
```

#### 方式 3：测试验证

```bash
cd /home/ubuntu/openvela_contest/contest2026_151_mianbao/cloud
python3 test_web.py
```

### 7.5 访问地址

启动后在浏览器中打开：
- **本地访问**: http://localhost:5000
- **远程访问**: http://服务器IP:5000

### 7.6 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│                    AI模拟面试官 - 面试记录                   │
├──────────────────────────────┬──────────────────────────────┤
│   🎤 面试控制                │   📊 面试评价                │
│   ┌────────────────────┐    │   ┌────────────────────┐    │
│   │ 选择岗位: [▼ 产品经理]│    │   │   8.5/10 分       │    │
│   │ 面试风格: [▼ 标准面试]│    │   │   逻辑: 8 专业: 9 │    │
│   │ [🚀 开始面试]       │    │   │   表达: 8          │    │
│   └────────────────────┘    │   └────────────────────┘    │
│                              │                              │
│   💬 面试对话                │   📚 历史记录                │
│   ┌────────────────────┐    │   ┌────────────────────┐    │
│   │ 🤖 请介绍一下你自己 │    │   │ 7月13日 产品经理    │    │
│   │ 👤 我是...          │    │   │ 7月12日 前端开发    │    │
│   └────────────────────┘    │   └────────────────────┘    │
│                              │                              │
│   输入回答: [____________]   │                              │
│   [📤 提交回答]             │                              │
└──────────────────────────────┴──────────────────────────────┘
```

### 7.7 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 管理界面 |
| `/api/health` | GET | 健康检查 |
| `/api/interview` | POST | 面试问答接口 |
| `/api/history` | GET | 获取历史记录 |

### 7.8 使用流程

1. **启动服务**：运行 `./start_web.sh` 或 `python3 app.py`
2. **访问界面**：在浏览器中打开 http://localhost:5000
3. **开始面试**：选择岗位和风格，点击"开始面试"
4. **进行面试**：在输入框中输入回答，点击"提交回答"
5. **查看评价**：面试结束后，右侧显示评价报告
6. **查看历史**：右侧面板显示历史面试记录

### 7.9 详细说明

完整的使用说明请查看：`cloud/WEB_INTERFACE.md`

包含：
- 界面布局说明
- 操作步骤详解
- API 接口文档
- 故障排除指南
- 开发说明

---

## 八、时间线更新

> 更新时间：2026-07-13

| 阶段 | 时间 | 任务 | 状态 |
|------|------|------|------|
| **环境搭建** | 7月9日-7月12日 | 开发环境配置、API 集成、日志工具 | ✅ 完成 |
| **代码验证** | 7月13日 | 硬件烧录、集成测试 | ✅ 完成 |
| **Web界面开发** | 7月13日 | Web 管理界面开发、文字面试功能 | ✅ 完成 |
| **正式开发** | 7月16日-7月20日 | 完善端侧功能、云端 API、音频集成 | ⏳ 待开始 |
| **端云联调** | 7月21日-7月25日 | 完整功能测试、语音+文字面试 | ⏳ 待开始 |
| **优化完善** | 7月26日-8月 | 性能优化、Prompt 调优、UI 美化 | ⏳ 待开始 |
| **最终演示** | 9月20日前 | 提交作品 | ⏳ 待开始 |

### 7月13日完成的工作

1. ✅ **硬件烧录验证**
   - 成功将代码编译并烧录到 R528 开发板
   - 验证了符号链接集成方式
   - 测试程序 `ai_interview_test` 运行正常

2. ✅ **Web 管理界面开发**
   - 创建了完整的 Web 界面（`cloud/templates/index.html`）
   - 实现了文字形式的面试功能
   - 添加了评价报告和历史记录功能
   - 编写了详细的使用说明文档

3. ✅ **项目文档更新**
   - 更新了 `project_status.md` 文档
   - 添加了 Web 界面使用指南
   - 记录了硬件烧录流程
