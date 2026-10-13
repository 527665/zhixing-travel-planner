import asyncio
import os
import selectors
import sys

# 确保项目根目录在 sys.path 中（支持命令行直接运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 下 psycopg 异步需要 Selector 事件循环
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from app.config import settings
from app.utils.logger import app_logger
from app.models import Base  # noqa: F401  确保业务模型注册到 metadata
from app.models.base import init_db


async def init_database():
    """初始化所有数据库表"""
    db_url = settings.database_url
    app_logger.info(f"连接数据库: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")

    try:
        # 1. 初始化业务表（用户、会话、消息）
        app_logger.info("初始化业务表...")
        await init_db()
        app_logger.info("业务表创建成功")

        # 2. 统一连接池：Checkpointer / Store / pgvector 共用
        #    autocommit=True：setup() 内部迁移含 CREATE INDEX CONCURRENTLY，
        #    该语句不能在事务块内执行，故初始化阶段需关闭事务包装
        async with AsyncConnectionPool(
            conninfo=db_url, min_size=2, max_size=10,
            kwargs={"autocommit": True},
        ) as pool:
            app_logger.info("初始化 Checkpointer 表...")
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            app_logger.info("Checkpointer 表创建成功")

            # 3. 初始化 Store 表
            app_logger.info("初始化 Store 表...")
            store = AsyncPostgresStore(pool)
            await store.setup()
            app_logger.info("Store 表创建成功")

            # 4. 启用 pgvector 扩展
            app_logger.info("启用 pgvector 扩展...")
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    await conn.commit()
            app_logger.info("pgvector 扩展启用成功")

        app_logger.info("数据库初始化完成!")

    except Exception as e:
        app_logger.error(f"数据库初始化失败: {e}")
        raise


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        # psycopg 异步连接不能运行在 Windows ProactorEventLoop 上。
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(init_database())
        finally:
            loop.close()
    else:
        asyncio.run(init_database())
