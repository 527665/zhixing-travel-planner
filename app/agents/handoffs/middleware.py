"""旧导入路径兼容层。请从 :mod:`app.core.middleware` 导入中间件。"""

from app.core.middleware import StepConfigMiddleware, create_step_config_middleware

__all__ = ["StepConfigMiddleware", "create_step_config_middleware"]
