"""测试天气 MCP Server"""

import asyncio

import pytest

from app.mcp_core.servers.weather_server import get_weather_forecast


@pytest.mark.asyncio
async def test_weather_forecast():
    """测试查询西安和北京的天气预报"""

    print("=== 测试西安天气 (adcode: 610100) ===")
    # @mcp.tool() 会把函数包装成 FunctionTool；.fn 是原始异步函数。
    result = await get_weather_forecast.fn("610100")
    print(result)

    print("\n=== 测试北京天气 (adcode: 110000) ===")
    result = await get_weather_forecast.fn("110000")
    print(result)


if __name__ == "__main__":
    asyncio.run(test_weather_forecast())
