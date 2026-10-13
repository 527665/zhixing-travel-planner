"""Handoffs 主 Agent 交互式测试"""

import asyncio
from pathlib import Path
import sys
import uuid

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 直接执行本文件时，将项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.handoffs.travel_agent import create_travel_agent
from app.core.checkpointer import CheckpointerManager
from app.mcp_core.client import MCPClientManager

async def run_interactive_chat():
    """运行持续对话的测试循环。"""
    # 1. 生成一个唯一的会话 ID，供 Checkpointer 区分会话历史
    try:
        travel_agent = await create_travel_agent()

        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        print(f"=== 开始测试 (会话 ID: {thread_id}) ===")
        print("输入 'q', 'quit', 'exit' 退出对话")
        print("-" * 50)

        while True:
            try:
                # 2. 获取用户输入，避免阻塞异步事件循环
                user_input = await asyncio.to_thread(input, "\nUser (你): ")
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.lower() in ["q", "quit", "exit"]:
                    print("结束对话。")
                    break

                # 3. 构造输入状态
                inputs = {"messages": [HumanMessage(content=user_input)]}

                # 4. 运行 Agent 并流式获取输出
                print("\nAssistant (Agent): ", end="", flush=True)
                last_message_key = None

                async for event in travel_agent.astream(
                    inputs,
                    config=config,
                    stream_mode="values",
                ):
                    messages = event.get("messages", [])
                    if not messages:
                        continue

                    last_msg = messages[-1]
                    # stream 会输出每一步状态，因此需要跳过重复消息
                    message_key = (
                        getattr(last_msg, "id", None),
                        type(last_msg).__name__,
                        getattr(last_msg, "name", None),
                        str(last_msg.content),
                    )
                    if message_key == last_message_key:
                        continue

                    last_message_key = message_key

                    # 只打印 AI 回复；工具消息单独显示工具名
                    if isinstance(last_msg, AIMessage) and last_msg.content:
                        print(last_msg.content)
                    elif isinstance(last_msg, ToolMessage):
                        print(f"\n[系统日志] 工具执行完毕: {last_msg.name}")

            except (EOFError, KeyboardInterrupt):
                print("\n结束对话。")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                import traceback
                traceback.print_exc()
    finally:
        # 交互结束后释放 MCP 和 PostgreSQL 连接池，避免后台任务阻止进程退出
        mcp_manager = MCPClientManager._instance
        if mcp_manager is not None:
            await mcp_manager.close()
            MCPClientManager.reset_instance()

        checkpointer_manager = CheckpointerManager._instance
        if checkpointer_manager is not None:
            await checkpointer_manager.close()
            CheckpointerManager._instance = None


if __name__ == "__main__":
    asyncio.run(run_interactive_chat())
