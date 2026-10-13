"""测试搜索 MCP Server"""

import asyncio
import json
import sys

import pytest

from app.mcp_core.servers.search_server import search_travel_info


def _print_result(result: str) -> None:
    """兼容 Windows 非 UTF-8 控制台，避免特殊字符导致输出失败。"""

    encoding = sys.stdout.encoding or "utf-8"
    safe_result = result.encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe_result)


def _assert_search_success(result: str, expected_query: str) -> dict:
    """检查搜索服务是否返回了有效且非错误的 JSON。"""

    data = json.loads(result)
    assert "error" not in data, f"搜索服务返回错误: {data}"
    assert data.get("query") == expected_query
    assert isinstance(data.get("results"), list)
    return data


@pytest.mark.asyncio
async def test_search_travel_info():
    """测试景点搜索和带结果数量限制的美食搜索"""

    print("=== 测试景点搜索 ===")
    # @mcp.tool() 会把函数包装成 FunctionTool；.fn 是原始异步函数。
    query = "西安必去景点推荐"
    result = await search_travel_info.fn(query)
    _print_result(result)
    _assert_search_success(result, query)

    print("\n=== 测试美食搜索 ===")
    query = "西安特色美食小吃"
    result = await search_travel_info.fn(query, 3)
    _print_result(result)
    data = _assert_search_success(result, query)
    assert len(data["results"]) <= 3


if __name__ == "__main__":
    asyncio.run(test_search_travel_info())
