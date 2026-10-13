"""
日志配置模块
使用 loguru 提供增强日志功能
"""
import os
import sys
from datetime import datetime
from loguru import logger
from app.config import settings, BASE_DIR

# 日志目录：项目根下的 logs/
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger():
    """配置日志系统"""
    # 移除默认处理器（同时保证重复调用不会叠加）
    logger.remove()

    # 控制台日志 (开发环境彩色输出)
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level="DEBUG" if settings.debug else "INFO"
    )

    # 文件日志 (JSON 格式，便于日志分析)
    log_file_path = os.path.join(LOG_DIR, "app.log")

    logger.add(
        log_file_path,
        rotation="500 MB",    # 日志轮转
        retention="10 days",   # 保留时间
        compression="zip",    # 压缩
        serialize=True,        # JSON 格式
        level="INFO"
    )

    # 错误日志单独记录
    logger.add(
        os.path.join(LOG_DIR, "error.log"),
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        level="ERROR"
    )

    logger.info("日志系统初始化完成")
    return logger


# 导出配置好的 Logger
app_logger = setup_logger()
