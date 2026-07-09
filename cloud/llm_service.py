"""
AI模拟面试官 — LLM 大模型服务
负责：C同学
"""
import json, logging
logger = logging.getLogger(__name__)
MIMO_LLM_API_URL = "https://api.mimo.xiaomi.com/v1/chat/completions"
MIMO_API_KEY = "your_api_key_here"

def llm_interview(role: str, history: list, state: str) -> dict:
    try:
        logger.info(f"LLM: 模拟调用，岗位={role}, 历史记录数={len(history)}")
        # TODO: 替换为真实的 xiaomi mimo LLM API 调用
        ai_text = "请简要介绍一下你自己和你为什么适合这个岗位。"
        next_action = "continue"
        if len(history) > 20:
            next_action = "finish"
            ai_text = "感谢你参加本次面试。以下是你的面试评估报告..."
        return {"text": ai_text, "next_action": next_action}
    except Exception as e:
        logger.error(f"LLM 调用失败: {str(e)}")
        return {"text": "抱歉，我暂时无法生成问题，请稍后再试。", "next_action": "continue"}
