"""
消息相关的 Pydantic 模型
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """创建消息"""

    # 上限既防超大请求体打爆上下文（一次长回复 = 真金白银的 token），
    # 也防有人拿几万字垃圾内容反复刷接口。
    content: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """消息响应"""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    extra_info: dict
    created_at: datetime

    # 与当前项目的 SQLAlchemy Message 模型兼容。
    model_config = ConfigDict(from_attributes=True)
