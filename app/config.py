import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache

# 获取当前文件的上级目录 (即项目根目录)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings(BaseSettings):
    """应用配置"""

    # ============ 应用基础配置 ============
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    # 允许跨域访问前端页面的来源，逗号分隔；公开部署时收紧到自己的域名
    cors_allow_origins: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080",
        alias="CORS_ALLOW_ORIGINS",
    )
    # 本机开发时前端常直接双击 HTML 打开（Origin 为 null），
    # 或用任意随机端口起静态服务器，正则兜住这两类，避免自断调试路。
    # 上线后把这条改成 ^https://你的域名$ 或直接留空。
    cors_allow_origin_regex: str = Field(
        default=r"^(http://(localhost|127\.0\.0\.1)(:\d+)?|null)$",
        alias="CORS_ALLOW_ORIGIN_REGEX",
    )

    # ============ LLM 配置 ============
    dashscope_api_key: str = Field(alias="LLM_API_KEY")  # 改这里
    qwen_model_name: str = Field(default="qwen-plus", alias="LLM_MODEL_NAME")  # 改这里
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="LLM_BASE_URL"  # 改这里
    )
    qwen_temperature: float = 0.7
    qwen_max_tokens: int = Field(default=8000, alias="LLM_MAX_TOKENS")

    # ============ LangSmith 配置 ============
    langsmith_api_key: str = Field(alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="zhixing-travel-planner-dev", alias="LANGSMITH_PROJECT")
    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT"
    )

    # ============ 数据库配置 ============
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # ============ MCP 服务配置 ============
    amap_api_key: str = Field(default="", alias="AMAP_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # ============ JWT 配置 ============
    # 留空时退化到复用 LLM 密钥，并打一条 warning，老环境不改 .env 也能跑
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, alias="JWT_EXPIRE_MINUTES")

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),    # 自动拼接路径，不管代码在哪运行都能找到
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"               # 忽略 .env 中多余的字段，防止报错
    )

    @property
    def database_url(self) -> str:
        """生成 PostgreSQL 连接字符串"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """生成 Redis 连接字符串"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins(self) -> list[str]:
        """把逗号分隔的字符串拆成 FastAPI 需要的来源列表"""
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取配置单例 (缓存) """
    return Settings()


# 全局配置对象
settings = get_settings()

# 测试
# if __name__ == '__main__':
#     print(settings.database_url)
#     print(settings.redis_url)
#     print(settings.qwen_model_name)
#     print(settings.qwen_base_url)
#     print(settings.qwen_temperature)
#     print(settings.qwen_max_tokens)
#     print(settings.langsmith_api_key)
