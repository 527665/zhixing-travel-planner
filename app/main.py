"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1 import chat, conversations, users
from app.config import settings
from app.utils.logger import app_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import asyncio

    # 打印当前事件循环信息（调试用）
    loop = asyncio.get_running_loop()
    app_logger.info(
        f"FastAPI 使用的事件循环: {type(loop).__name__}"
    )

    # 延迟导入，避免应用模块导入时立即初始化外部资源。
    from app.core.checkpointer import checkpointer_lifespan
    from app.core.store import store_lifespan
    from app.mcp_core.client import MCPClientManager

    app_logger.info("🚀 启动应用...")

    async with checkpointer_lifespan():
        app_logger.info("✅ Checkpointer 已就绪")

        async with store_lifespan():
            app_logger.info("✅ Store 已就绪")

            # get_instance() 首次创建时会自动初始化 MCP 客户端。
            mcp = await MCPClientManager.get_instance()
            app_logger.info("✅ MCP 服务初始化成功")

            try:
                yield
            finally:
                await mcp.close()
                MCPClientManager.reset_instance()
                app_logger.info("MCP 服务已关闭")

    app_logger.info("应用已关闭")


app = FastAPI(
    title="知行 ZhiXing · 智能旅行规划助手",
    description="基于 LangGraph 的多 Agent 旅行规划服务：需求收集、目的地推荐、交通、住宿、餐饮、行程、预算、订单",
    version="1.0.0",
    lifespan=lifespan,
)

class MaxBodySizeMiddleware:
    """
    请求体大小上限（纯 ASGI 中间件）

    为什么用纯 ASGI 而不是 @app.middleware("http")：
        后者是 BaseHTTPMiddleware，会把响应重新装进一条内存管道，
        对 SSE 流式接口不友好；纯 ASGI 只在收包路径上加一层计数，
        不碰发送路径，流式响应原样穿过。

    两道判定：
        1. 先看 Content-Length 头，明显超限就直接回 413，一个字节都不读；
        2. 没有 Content-Length（分块传输）时，边收边累加，
           超过上限就把后续 body 掐断，交给业务层得到残缺 JSON -> 400/422，
           同样不会走到 LLM，不花钱。
    """

    def __init__(self, app, max_bytes: int = 1 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    @staticmethod
    def _header(scope: dict, name: str) -> str | None:
        """从 ASGI scope 里取请求头（小写比较）"""
        for key, value in scope.get("headers", []):
            if key.decode("latin-1").lower() == name:
                return value.decode("latin-1")
        return None

    async def _reject(self, scope, send, reason: str):
        app_logger.warning(
            f"🚫 拒绝超大请求体: {scope.get('method')} {scope.get('path')} {reason}"
        )
        response = JSONResponse(
            status_code=413,
            content={"code": 413, "msg": "请求体过大", "data": None},
        )
        await response(scope, receive=None, send=send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = self._header(scope, "content-length")
        if declared:
            try:
                if int(declared) > self.max_bytes:
                    await self._reject(scope, send, f"声明 {declared} 字节")
                    return
            except ValueError:
                await self._reject(scope, send, "Content-Length 非法")
                return

        state = {"received": 0, "truncated": False}

        async def counting_receive():
            message = await receive()
            if message["type"] != "http.request":
                return message
            if state["truncated"]:
                # 已经掐断：不再把剩余字节交给业务层
                return {"type": "http.request", "body": b"", "more_body": False}
            body = message.get("body", b"")
            state["received"] += len(body)
            if state["received"] > self.max_bytes:
                state["truncated"] = True
                app_logger.warning(
                    f"🚫 分块请求体超过上限 {self.max_bytes} 字节，已掐断: "
                    f"{scope.get('method')} {scope.get('path')}"
                )
                return {"type": "http.request", "body": b"", "more_body": False}
            return message

        await self.app(scope, counting_receive, send)


# 注意添加顺序：后注册的中间件在外层。
# 限流/体积校验先注册（内层），CORS 后注册（外层），
# 这样 413 / 429 这类错误响应也会带上跨域头，前端能正常读到报错。
app.add_middleware(MaxBodySizeMiddleware, max_bytes=1 * 1024 * 1024)
app.add_middleware(
    CORSMiddleware,
    # 收紧来源白名单：["*"] 与 allow_credentials=True 是错误示范，
    # 浏览器在带凭证时本来就不会放行通配来源，公开部署必须显式列域名。
    allow_origins=settings.cors_origins,
    # 正则白名单兜住本机调试（file:// 打开时 Origin 是 null，随机端口也要放行）
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# 注册 v1 API 路由
app.include_router(users.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "ZhiXing Travel Planner",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health_check():
    """详细健康检查"""
    from app.core.checkpointer import get_checkpointer
    from app.core.store import get_store

    try:
        await get_checkpointer()
        await get_store()

        return {
            "status": "healthy",
            "components": {
                "checkpointer": "ready",
                "store": "ready",
                "llm": "configured",
            },
        }
    except Exception as e:
        app_logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
