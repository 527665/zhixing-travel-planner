"""
交通规划协调器（主 Agent）
整合高铁、自驾 Subagent 和辅助 MCP 工具
"""

import asyncio

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from app.config import settings
from app.agents.subagents.train_agent import create_train_subagent
from app.agents.subagents.driving_agent import create_driving_subagent
from app.mcp_core.client import get_mcp_client
from app.utils.logger import app_logger


# 当前项目已经接通并启用的 MCP 服务。
# 先统一初始化它们，避免 MCP 单例被某个 Subagent 提前锁定。
ENABLED_MCP_SERVERS = ["amap", "12306-mcp"]


async def _get_auxiliary_tools():
    """获取天气、日期、周边搜索等辅助工具"""

    manager = await get_mcp_client(servers=ENABLED_MCP_SERVERS)
    all_tools = await manager.get_tools()

    auxiliary_tools = [
        tool
        for tool in all_tools
        if any(
            keyword in tool.name.lower()
            for keyword in [
                "getfutureweatherbyairport",
                "get-current-date",
                "maps_around_search",
            ]
        )
    ]

    app_logger.info(f"辅助工具: {[tool.name for tool in auxiliary_tools]}")
    return auxiliary_tools


async def create_transport_coordinator():
    """
    创建交通规划协调器（主 Agent）

    整合：
    - 高铁查询 Subagent
    - 自驾路线规划 Subagent
    - MCP 辅助工具

    航班工具目前暂不启用，恢复航班服务后再加入。
    """

    llm = ChatOpenAI(
        model=settings.qwen_model_name,
        base_url=settings.qwen_base_url,
        api_key=settings.dashscope_api_key,
        temperature=0.7,
    )

    # 先统一初始化 MCP 单例，再创建依赖其中工具的 Subagent
    await get_mcp_client(servers=ENABLED_MCP_SERVERS)

    train_subagent = await create_train_subagent()
    driving_subagent = await create_driving_subagent()

    @tool(
        "query_trains",
        description="查询高铁/火车信息。需要提供出发城市、目的地城市、出发日期。",
    )
    async def query_trains_tool(
        origin: str,
        destination: str,
        departure_date: str,
    ) -> str:
        """查询高铁信息（调用高铁 Subagent）"""

        app_logger.info(f"调用高铁 Subagent: {origin} -> {destination}")

        result = await train_subagent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"请查询从 {origin} 到 {destination} 的高铁，"
                            f"出发日期是 {departure_date}。"
                        ),
                    }
                ]
            }
        )

        return result["messages"][-1].content

    @tool(
        "plan_driving_route",
        description="规划自驾路线。需要提供出发地和目的地（地址或地名）。",
    )
    async def plan_driving_route_tool(
        origin: str,
        destination: str,
    ) -> str:
        """规划自驾路线（调用自驾 Subagent）"""

        app_logger.info(f"调用自驾 Subagent: {origin} -> {destination}")

        result = await driving_subagent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"请规划从 {origin} 到 {destination} 的自驾路线。",
                    }
                ]
            }
        )

        return result["messages"][-1].content

    auxiliary_tools = await _get_auxiliary_tools()

    coordinator_tools = [
        query_trains_tool,
        plan_driving_route_tool,
    ] + auxiliary_tools

    coordinator = create_agent(
        model=llm,
        tools=coordinator_tools,
        system_prompt="""你是交通规划协调专家。

**可用工具**：

**交通查询**：
1. query_trains：查询高铁信息（适合中短途，舒适便捷）
2. plan_driving_route：规划自驾路线（适合深度游，自由灵活）

**辅助工具**：
- get-current-date：获取今天日期，调用需要日期的工具前应先使用。
- maps_around_search：查询路线或目的地周边的地点信息。

**工作流程**：
1. 理解用户的交通需求（出发地、目的地、日期、人数）。
2. 如果用户明确指定交通方式，直接调用对应工具。
3. 如果用户未指定，根据距离和用户偏好推荐高铁或自驾。
4. 涉及“今天、明天、下周”等相对日期时，先调用 get-current-date。
5. 调用工具后，用清晰的格式展示结果。
6. 如果查询失败，告知用户并提供替代方案。

**注意事项**：
- 一定要调用工具获取实时信息，不要编造数据。
- 高铁查询需要提供日期，自驾路线查询需要起点和终点。
- 只有在工具返回真实结果后，才能向用户报告距离、时间、价格等数据。
""",
    )

    app_logger.info("交通规划协调器（主 Agent）创建完成")
    return coordinator


if __name__ == "__main__":

    async def main():
        print("\n" + "=" * 50)
        print("正在初始化交通规划协调器...")
        print("=" * 50)

        coordinator = await create_transport_coordinator()
        test_query = "我想从北京去上海，明天出发，帮我推荐交通方式"

        print(f"\n用户提问: {test_query}")
        print("-" * 30)

        response = await coordinator.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": test_query}
                ]
            }
        )

        print("-" * 30)
        print("协调器回复:")
        print(response["messages"][-1].content)

        print("\n" + "=" * 50)
        print("测试结束")
        print("=" * 50)

    asyncio.run(main())
