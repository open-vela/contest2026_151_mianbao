# AI模拟面试官 — 项目启动状态总结

> 生成时间：2026-07-09  
> 负责：项目负责人  

---

## 一、已完成的工作

### 1.1 开题报告
- ✅ 技术方案已确定（详见 test-project/开题报告_详细设计方案.md v1.3）
- ✅ 4人分工明确（A: 硬件集成 / B: 端侧状态机 / C: 云端服务 / D: Skill+Prompt）
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

## 二、当前状态

| 模块 | 状态 | 负责 | 下一步动作 |
|------|------|------|-----------|
| 状态机 | 骨架完成 | B | 完善状态机逻辑 + 实现录音控制 |
| 云端服务 | 骨架完成 | C | 获取 xiaomi mimo API 密钥 + 替换模拟代码 |
| 网络通信 | 骨架完成 | A | 实现 HTTPS POST 发送+接收 |
| Skill Prompt | 模板完成 | D | 注册到 ai_agent 框架 + 迭代优化 |
| 硬件驱动 | 未开始 | A | 烧录镜像 + 验证驱动 |
| 联调 | 未开始 | 全员 | 7月下旬第一次联调 |

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
