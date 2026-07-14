# AI模拟面试官 — 云端服务（纯后端 API）

> 负责：C同学
> 更新时间：2026-07-14
> 正式开发开始：2026-07-16

---

## 一、项目简介

本目录包含 AI 模拟面试官的**云端后端服务**，基于 Flask 框架构建，集成小米 MIMO API 提供 ASR（语音识别）、TTS（语音合成）和 LLM（大语言模型）能力。Web 前端界面已迁移至 `test-project/web_frontend/` 目录。

---

## 二、目录结构

```
cloud/
├── app.py                  # Flask 主程序（纯后端 API）
├── asr_service.py          # ASR 语音识别服务
├── tts_service.py          # TTS 语音合成服务
├── llm_service.py          # LLM 大语言模型服务
├── session_manager.py      # 会话管理模块
├── requirements.txt        # Python 依赖列表
│
├── test_services.py        # ASR/TTS 服务测试脚本
├── play_tts.py             # TTS 语音播放工具
├── demo_interview.py       # 面试流程演示脚本
│
└── README.md               # 本文件
```

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

- ⏳ 骨架代码（待完善）

### 3.4 会话管理 (`session_manager.py`)

- ⏳ 骨架代码（待完善）

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

使用环境变量配置小米 MIMO API Key：

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
# 设置 API Key
export MIMO_API_KEY="sk-你的API密钥"

# 启动服务
python3 app.py
```

服务启动后，可以访问以下地址：
- **Web 管理界面**: http://localhost:5000
- **API 接口**: http://localhost:5000/api/
- **健康检查**: http://localhost:5000/api/health

### 5.5 使用 Web 界面

1. **访问管理界面**
   在浏览器中打开 `http://服务器IP:5000`

2. **开始面试**
   - 选择面试岗位（产品经理、前端开发、后端开发等）
   - 选择面试风格（标准、压力、友好、技术）
   - 点击"开始面试"按钮

3. **进行面试**
   - 在输入框中输入你的回答
   - 点击"提交回答"或按回车键
   - AI 面试官会自动生成下一个问题

4. **查看评价**
   - 面试结束后，系统会自动生成评价报告
   - 包含综合评分、各维度评分和详细评价

5. **查看历史**
   - 右侧面板显示历史面试记录
   - 点击记录可查看详情

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

### 6.4 Web 界面技术说明

**技术栈**：
- 前端：原生 HTML + CSS + JavaScript（单文件，无依赖）
- 后端：Flask + RESTful API
- 通信：Fetch API + JSON

**主要功能**：
| 功能 | 说明 |
|------|------|
| 面试控制 | 选择岗位、风格，开始/结束面试 |
| 实时对话 | 显示面试问答过程 |
| 评价报告 | 展示综合评分和详细评价 |
| 历史记录 | 查看过往面试记录 |

**API 端点**：
```
GET  /                  # Web 管理界面
GET  /api/health        # 健康检查
POST /api/interview     # 面试问答接口
GET  /api/history       # 获取历史记录
```

**页面布局**：
- 左侧面板：面试控制、对话区域
- 右侧面板：评价报告、历史记录
- 响应式设计：支持移动端访问

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

## 八、下一步计划

> ⚠️ 正式开发从 **7月16日** 开始，以下为开发启动后的计划

### 第一阶段（7月16日 - 7月20日）

1. **完善 Flask API** (`app.py`)
   - `/asr` 接口：接收音频，返回识别文字
   - `/tts` 接口：接收文字，返回音频
   - `/interview` 接口：完整的面试问答流程

2. **集成 LLM 服务** (`llm_service.py`)
   - 对接小米 MIMO LLM API ✅ 已完成
   - 实现面试问答逻辑 ✅ 已完成
   - 与 Flask API 集成

### 第二阶段（7月21日 - 7月25日）

3. **完善会话管理** (`session_manager.py`)
   - 面试状态维护
   - 对话历史记录

4. **端云联调**
   - 端侧录音 → 云端 ASR → LLM → TTS → 端侧播放
   - 完整面试流程测试

---

## 九、负责人

- **A同学**：云端服务器开发、ASR/TTS 集成

---

## 十、相关文档

- [项目状态文档](../documents/project_status.md)
- [API 协议文档](../documents/api_protocol.md)
- [小米 MIMO ASR 文档](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition)
- [小米 MIMO TTS 文档](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Text-to-Speech)
