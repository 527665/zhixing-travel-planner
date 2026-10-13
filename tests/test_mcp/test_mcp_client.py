"""测试 MCP 客户端"""

import asyncio
import json
import sys

import pytest

from app.mcp_core.client import MCPClientManager


def _safe_print(value="") -> None:
    """兼容 Windows 非 UTF-8 控制台，避免特殊字符导致输出失败。"""

    text = str(value)
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding))


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前后重置单例"""

    MCPClientManager.reset_instance()
    yield
    MCPClientManager.reset_instance()


@pytest.mark.asyncio
async def test_print_mcp_tools():
    """测试打印所有 MCP 工具"""

    _safe_print("\n" + "=" * 60)
    _safe_print("🚀 正在初始化 MCP 客户端管理器...")

    manager = await MCPClientManager.get_instance(
        servers=[
            "weather",
            "search",
            "amap",
            "12306-mcp",
            "VariFlight-Aviation",
            "aigohotel-mcp",
        ]
    )

    try:
        # 获取所有 MCP 工具
        tools = await manager.get_tools()

        _safe_print(f"✅ 连接成功！共发现 {len(tools)} 个工具")
        _safe_print("=" * 60)

        # 打印工具详情
        for i, tool in enumerate(tools, 1):
            _safe_print(f"🛠️  工具 [{i}]")
            _safe_print(f"📌 名称: {tool.name}")
            _safe_print(f"📝 描述: {tool.description}")
            _safe_print("⚙️  参数结构:")
            try:
                _safe_print(
                    json.dumps(
                        tool.args,
                        indent=2,
                        ensure_ascii=False
                    )
                )
            except Exception:
                _safe_print(f"   {tool.args}")
            _safe_print("-" * 60)

        assert len(tools) > 0, "应该至少有一个工具"

    finally:
        _safe_print("\n🔌 正在关闭连接...")
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_print_mcp_tools())
