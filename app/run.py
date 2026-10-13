#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动脚本 - Windows 兼容版本（强制 SelectorEventLoop）
"""

import asyncio
import selectors
import sys
from pathlib import Path


# 必须在导入 Uvicorn 和应用模块之前设置事件循环。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
else:
    loop = asyncio.new_event_loop()

asyncio.set_event_loop(loop)

# 兼容从项目根目录执行 `python app/run.py`。
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn


if __name__ == "__main__":
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        loop="none",
    )
    server = uvicorn.Server(config)

    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()
