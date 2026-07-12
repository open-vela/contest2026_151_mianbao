"""
AI模拟面试官 — LLM 服务（小米 MIMO API）
负责：A同学（统一接口）
"""
import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# 小米 MIMO API 配置（与 ASR/TTS 统一）
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "sk-c31fef0fmk0aq1avis1f73xpekskcl6dyoixaobw8z2y63qn")
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
LLM_MODEL = "mimo-v2.5"

# 加载 Skills Prompt 模板
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def load_skill(skill_name: str) -> dict:
    """
    加载 Skill Prompt 模板

    Args:
        skill_name: Skill 名称（不含 .json 后缀）

    Returns:
        Skill 配置字典
    """
    skill_path = os.path.join(SKILLS_DIR, f"{skill_name}.json")
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            skill = json.load(f)
        logger.info(f"加载 Skill: {skill_name}")
        return skill
    except Exception as e:
        logger.error(f"加载 Skill 失败: {e}")
        return {}


def call_llm(system_prompt: str, messages: list, temperature: float = 0.7,
             max_tokens: int = 500) -> str:
    """
    调用小米 MIMO LLM API

    Args:
        system_prompt: 系统提示词
        messages: 对话消息列表
        temperature: 温度参数
        max_tokens: 最大生成 token 数

    Returns:
        LLM 生成的文本
    """
    try:
        client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL
        )

        # 构建完整消息列表
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        logger.info(f"LLM 请求: model={LLM_MODEL}, 消息数={len(full_messages)}")

        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        result = completion.choices[0].message.content
        logger.info(f"LLM 返回: {result[:100]}...")
        return result

    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return ""


# ============================================================
# Skill 实现函数
# ============================================================

def start_interview(role: str) -> dict:
    """
    Skill: start_interview — 开始面试，生成第一个问题

    Args:
        role: 面试岗位，如 "产品经理"、"前端开发工程师"

    Returns:
        {"text": "面试问题", "next_action": "continue"}
    """
    skill = load_skill("start_interview")
    if not skill:
        return {"text": "抱歉，加载面试配置失败。", "next_action": "continue"}

    # 替换 system_prompt 中的变量
    system_prompt = skill["system_prompt"].replace("{role}", role)

    # 调用 LLM
    messages = [{"role": "user", "content": "请开始面试，提出第一个问题。"}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.7),
        max_tokens=skill.get("max_tokens", 500)
    )

    if result:
        return {"text": result, "next_action": "continue"}
    else:
        return {"text": "抱歉，生成问题失败，请重试。", "next_action": "continue"}


def next_question(role: str, history: list, last_answer: str) -> dict:
    """
    Skill: next_question — 根据用户回答生成下一个问题或追问

    Args:
        role: 面试岗位
        history: 完整对话历史 [{"role": "user"/"assistant", "content": "..."}]
        last_answer: 用户的最新回答

    Returns:
        {"text": "下一个问题", "next_action": "continue"}
    """
    skill = load_skill("next_question")
    if not skill:
        return {"text": "抱歉，加载面试配置失败。", "next_action": "continue"}

    system_prompt = skill["system_prompt"].replace("{role}", role)

    # 构建消息（包含历史）
    messages = list(history)
    messages.append({"role": "user", "content": f"候选人回答：{last_answer}\n\n请根据回答决定是追问还是提出新问题。"})

    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.7),
        max_tokens=skill.get("max_tokens", 800)
    )

    # 判断是否结束面试（超过 10 轮）
    next_action = "finish" if len(history) >= 20 else "continue"

    if result:
        return {"text": result, "next_action": next_action}
    else:
        return {"text": "抱歉，生成问题失败，请重试。", "next_action": "continue"}


def evaluate_answer(role: str, question: str, answer: str) -> dict:
    """
    Skill: evaluate_answer — 对单个回答进行打分和点评

    Args:
        role: 面试岗位
        question: 面试问题
        answer: 用户回答

    Returns:
        {"text": "点评", "score": 8, "dimensions": {"logic": 8, "professionalism": 7, "clarity": 9}}
    """
    skill = load_skill("evaluate_answer")
    if not skill:
        return {"text": "评估失败", "score": 0, "dimensions": {}}

    system_prompt = skill["system_prompt"].replace("{role}", role)

    user_content = f"问题：{question}\n候选人回答：{answer}\n\n请从逻辑性、专业性、表达清晰度三个维度打分（1-10），并给出简短点评。"

    messages = [{"role": "user", "content": user_content}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.5),
        max_tokens=skill.get("max_tokens", 400)
    )

    if result:
        # 简单解析（实际可优化为 JSON 格式输出）
        return {"text": result, "score": 0, "dimensions": {}}
    else:
        return {"text": "评估失败", "score": 0, "dimensions": {}}


def generate_feedback(role: str, history: list) -> dict:
    """
    Skill: generate_feedback — 面试结束生成完整评估报告

    Args:
        role: 面试岗位
        history: 完整对话历史

    Returns:
        {"text": "评估报告", "next_action": "finish"}
    """
    skill = load_skill("generate_feedback")
    if not skill:
        return {"text": "生成报告失败", "next_action": "finish"}

    system_prompt = skill["system_prompt"].replace("{role}", role)

    # 构建对话摘要
    conversation = "\n".join([f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}" for m in history])
    user_content = f"以下是完整面试对话：\n\n{conversation}\n\n请生成详细的面试评估报告。"

    messages = [{"role": "user", "content": user_content}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.7),
        max_tokens=skill.get("max_tokens", 1000)
    )

    if result:
        return {"text": result, "next_action": "finish"}
    else:
        return {"text": "生成报告失败", "next_action": "finish"}


def check_timeout(role: str, timeout_duration: int, partial_answer: str = "") -> dict:
    """
    Skill: check_timeout — 用户回答超时打断

    Args:
        role: 面试岗位
        timeout_duration: 超时时长（秒）
        partial_answer: 用户已录制的部分内容

    Returns:
        {"text": "超时提示", "next_action": "continue"}
    """
    skill = load_skill("check_timeout")
    if not skill:
        return {"text": "您思考的时间比较长了，可以先简单回答一下吗？", "next_action": "continue"}

    system_prompt = skill["system_prompt"].replace("{role}", role).replace("{timeout_duration}", str(timeout_duration))

    user_content = f"候选人已思考 {timeout_duration} 秒"
    if partial_answer:
        user_content += f"，已录制的部分内容：{partial_answer}"
    user_content += "\n\n请礼貌地提示候选人可以先做一个简要回答。"

    messages = [{"role": "user", "content": user_content}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.5),
        max_tokens=skill.get("max_tokens", 200)
    )

    if result:
        return {"text": result, "next_action": "continue"}
    else:
        return {"text": "您思考的时间比较长了，可以先简单回答一下吗？", "next_action": "continue"}


# ============================================================
# 兼容旧接口
# ============================================================

def llm_interview(role: str, history: list, state: str, audio_base64: str = "") -> dict:
    """
    兼容旧版接口（已被 skill 函数替代）
    """
    if state == "start":
        return start_interview(role)
    elif state == "evaluate":
        if history:
            last_q = history[-2]["content"] if len(history) >= 2 else ""
            last_a = history[-1]["content"] if history else ""
            return evaluate_answer(role, last_q, last_a)
    elif state == "feedback":
        return generate_feedback(role, history)
    else:
        if history:
            return next_question(role, history[:-1], history[-1]["content"])

    return start_interview(role)


# 测试
if __name__ == "__main__":
    print("LLM 服务模块已加载")
    print(f"API Key: {MIMO_API_KEY[:10]}..." if MIMO_API_KEY else "API Key: 未配置")
    print(f"Skills 目录: {SKILLS_DIR}")

    # 测试 start_interview
    print("\n测试 start_interview:")
    result = start_interview("产品经理")
    print(f"结果: {result}")
