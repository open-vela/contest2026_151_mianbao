# AI模拟面试官 — Skills Prompt

> 负责：D同学（Prompt 设计）、A同学（接口实现）  
> 更新时间：2026-07-12  
> 正式开发开始：2026-07-16

---

## 一、概述

本目录包含 AI 模拟面试官的 **5 个核心 Skills**，每个 Skill 对应面试流程中的一个环节。Skills 以 JSON 格式定义 Prompt 模板，由 `cloud/llm_service.py` 加载并调用小米 MIMO LLM API 执行。

---

## 二、Skills 清单

| # | Skill 文件 | 功能 | 触发时机 | 实现状态 |
|---|-----------|------|----------|----------|
| 1 | `start_interview.json` | 开始面试，生成第一个问题 | 用户按键开始面试 | ✅ 已完成 |
| 2 | `next_question.json` | 根据回答生成下一个问题或追问 | 接收到用户语音回答后 | ✅ 已完成 |
| 3 | `evaluate_answer.json` | 对单个回答打分和点评 | 每个回答之后 | ⏳ 待优化 |
| 4 | `generate_feedback.json` | 面试结束生成完整评估报告 | 面试结束 | ⏳ 待优化 |
| 5 | `check_timeout.json` | 用户回答超时打断逻辑 | 录音超过3分钟未停止 | ✅ 已完成 |

---

## 三、各 Skill 详细说明

### 1. `start_interview` — 开始面试

**功能**：根据应聘岗位生成第一个面试问题

**输入参数**：
- `role`：面试岗位（如"产品经理"、"前端开发工程师"）

**输出**：
```json
{
  "text": "面试官的第一轮提问",
  "next_action": "continue"
}
```

**实现状态**：✅ 已完成并测试

**测试结果**：
- 产品经理：✅ 生成合适问题
- 前端开发工程师：✅ 生成合适问题
- 测试工程师：✅ 生成合适问题
- 算法工程师：✅ 生成合适问题

---

### 2. `next_question` — 下一个问题

**功能**：根据用户回答判断是追问还是提出新问题

**输入参数**：
- `role`：面试岗位
- `history`：完整对话历史
- `last_answer`：用户的最新回答

**输出**：
```json
{
  "text": "下一个面试问题或追问",
  "next_action": "continue"
}
```

**实现状态**：✅ 代码已实现，待数据优化

**待优化项**：
- [ ] 收集真实面试对话数据，优化追问逻辑
- [ ] 测试不同岗位的追问质量
- [ ] 调整"追问 vs 新问题"的判断阈值

---

### 3. `evaluate_answer` — 评估回答

**功能**：对用户的单个回答进行打分和点评

**输入参数**：
- `role`：面试岗位
- `question`：面试问题
- `answer`：用户回答

**输出**：
```json
{
  "text": "打分和点评",
  "score": 8,
  "dimensions": {
    "logic": 8,
    "professionalism": 7,
    "clarity": 9
  }
}
```

**评分维度**：
- `logic`（逻辑性）：回答是否有条理、逻辑清晰
- `professionalism`（专业性）：是否体现专业知识和经验
- `clarity`（表达清晰度）：表达是否简洁明了

**实现状态**：⏳ 代码已实现，待数据优化

**待优化项**：
- [ ] 收集面试评分标准数据
- [ ] 定义各维度的评分细则（1-10 分标准）
- [ ] 优化 Prompt 使输出格式稳定（JSON 格式）
- [ ] 测试评分一致性

---

### 4. `generate_feedback` — 生成报告

**功能**：面试结束时生成完整的评估报告

**输入参数**：
- `role`：面试岗位
- `history`：完整对话历史

**输出**：
```json
{
  "text": "结构化面试评估报告",
  "next_action": "finish"
}
```

**报告结构**：
1. 总体评价
2. 优点
3. 待改进项
4. 综合建议

**实现状态**：⏳ 代码已实现，待数据优化

**待优化项**：
- [ ] 收集优秀面试评估报告样本
- [ ] 优化报告格式和内容结构
- [ ] 添加岗位针对性的评估标准

---

### 5. `check_timeout` — 超时处理

**功能**：用户思考时间过长时，礼貌地提示继续

**输入参数**：
- `role`：面试岗位
- `timeout_duration`：超时时长（秒）
- `partial_answer`：已录制的部分内容（可选）

**输出**：
```json
{
  "text": "超时打断提示语",
  "next_action": "continue"
}
```

**实现状态**：✅ 已完成

---

## 四、技术实现

### 4.1 调用链路

```
用户语音 → ASR → 文字 → Skill 函数 → LLM API → 回答文字 → TTS → 语音播放
```

### 4.2 代码位置

- **Skill 模板**：`skills/*.json`（本目录）
- **Skill 实现**：`cloud/llm_service.py`
- **LLM API**：小米 MIMO API（`mimo-v2.5` 模型）

### 4.3 调用示例

```python
from llm_service import start_interview, next_question, evaluate_answer

# 开始面试
result = start_interview("产品经理")
print(result["text"])  # 输出第一个问题

# 生成下一个问题
history = [
    {"role": "assistant", "content": "请介绍一下你自己"},
    {"role": "user", "content": "我是..."}
]
result = next_question("产品经理", history, "我是...")
print(result["text"])  # 输出下一个问题或追问

# 评估回答
result = evaluate_answer("产品经理", "请介绍一下你自己", "我是...")
print(result["text"])  # 输出评分和点评
```

---

## 五、数据需求

以下是各 Skill 优化所需的数据：

### 5.1 优先级：高

| 数据类型 | 用途 | 数量建议 | 负责 |
|---------|------|---------|------|
| 面试问题库 | 各岗位常见面试问题 | 每岗位 50+ 题 | D同学 |
| 参考答案 | 评估回答质量的基准 | 每问题 3 个水平 | D同学 |
| 评分标准 | evaluate_answer 维度定义 | 每维度 1-10 分细则 | D同学 |

### 5.2 优先级：中

| 数据类型 | 用途 | 数量建议 | 负责 |
|---------|------|---------|------|
| 面试对话流 | next_question 追问逻辑 | 20+ 完整对话 | D同学 |
| 评估报告样本 | generate_feedback 格式参考 | 10+ 份报告 | D同学 |

### 5.3 数据来源建议

1. **GitHub 面试题库**：JavaGuide、CS-Notes、fe-interview 等
2. **Hugging Face 数据集**：搜索 `interview chinese`
3. **LLM 生成**：用小米 MIMO 生成基础数据，人工审核
4. **真实面试记录**：收集同学的面试经历

---

## 六、下一步计划

> ⚠️ 正式开发从 **7月16日** 开始，以下为开发启动后的计划

### 第一阶段（7月16日 - 7月20日）

- [ ] D同学提交第一版 Prompt 优化
- [ ] 收集至少 3 个岗位的面试问题库
- [ ] 定义 evaluate_answer 评分细则
- [ ] 完成所有 Skill 的 Prompt 优化

### 第二阶段（7月21日 - 7月25日）

- [ ] 集成测试完整面试流程
- [ ] 根据测试结果迭代优化
- [ ] 优化追问逻辑的自然度

### 第三阶段（7月26日 - 8月）

- [ ] 收集真实面试数据进行微调
- [ ] 完善评估报告的专业性
- [ ] 最终联调与优化

---

## 七、负责人

| 任务 | 负责人 | 截止日期 |
|------|--------|---------|
| Skill JSON 模板 | D同学 | ✅ 已完成（7月9日） |
| Skill 代码实现 | A同学 | ✅ 已完成（7月12日） |
| Prompt 优化 | D同学 | 7月20日 |
| 数据收集 | D同学 | 7月25日 |
| 集成测试 | A同学、D同学 | 7月25日 |

---

## 八、相关文档

- [项目状态文档](../documents/project_status.md)
- [API 协议文档](../documents/api_protocol.md)
- [云端服务 README](../cloud/README.md)
- [小米 MIMO LLM 文档](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation)
