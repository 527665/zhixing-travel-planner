"""
会话相关的 Pydantic 模型
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    """创建会话"""

    title: Optional[str] = "新对话"


class ConversationUpdate(BaseModel):
    """更新会话"""

    title: Optional[str] = None
    status: Optional[str] = None


class ConversationResponse(BaseModel):
    """会话响应"""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    status: str
    extra_info: dict
    created_at: datetime
    updated_at: datetime

    # Pydantic 2 写法：允许从 SQLAlchemy 模型对象读取属性。
    model_config = ConfigDict(from_attributes=True)
