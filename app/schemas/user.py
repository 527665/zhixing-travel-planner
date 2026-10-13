"""
用户相关的 Pydantic 模型
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """用户注册"""

    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    # max_length=128：bcrypt 只用前 72 字节，超长部分本来就是废数据；
    # 卡上限同时防止有人 POST 几 MB 密码把 CPU 打满（哈希是昂贵的）。
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    """用户登录"""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    """用户信息响应"""

    id: uuid.UUID
    username: str
    email: str
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime

    # Pydantic 2 写法：允许从 SQLAlchemy 模型对象读取属性。
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """令牌响应"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
