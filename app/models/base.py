"""
SQLAlchemy 基础配置
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, declared_attr

from app.config import settings


class Base(DeclarativeBase):
    """基础模型类"""

    @declared_attr
    def __tablename__(cls) -> str:
        """自动生成表名（类名转小写）"""
        return cls.__name__.lower()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


# 创建异步引擎
# 项目已安装 psycopg，没有 asyncpg，因此使用 psycopg 异步方言。
engine = create_async_engine(
    settings.database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    ),
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)


# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
