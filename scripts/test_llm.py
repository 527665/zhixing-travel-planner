import os
import sys

# 确保项目根目录在 sys.path 中（支持命令行直接运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from app.config import settings
from app.utils.logger import app_logger


def test_llm():
    """最小 LLM 连通性测试：消耗最少 token 的问题"""
    app_logger.info(f"测试模型: {settings.qwen_model_name}")
    app_logger.info(f"API 端点: {settings.qwen_base_url}")

    llm = ChatOpenAI(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        base_url=settings.qwen_base_url,
        temperature=settings.qwen_temperature,
        max_tokens=settings.qwen_max_tokens,
    )

    question = "用最简洁的语句介绍一下自己"
    app_logger.info(f"发送问题: {question}")
    response = llm.invoke(question)
    app_logger.info(f"响应: {response.content}")
    app_logger.info("LLM 连接测试通过!")


if __name__ == "__main__":
    test_llm()
