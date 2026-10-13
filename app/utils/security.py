"""
安全工具（密码加密、JWT）
"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

from app.config import settings
from app.utils.logger import app_logger

# bcrypt 只处理前 72 字节，超长密码必须在哈希前手动截断，
# 否则 bcrypt 5.x 直接抛 ValueError；截断也顺带挡住了"超大密码 DoS"。
# 副作用（bcrypt 固有行为，不是 bug）：第 73 字节之后的内容不参与校验，
# 即 "72字节相同 + 后缀不同" 的两个密码会被判定为同一个。
# 因此 schema 里把密码上限压到 128 字符，提示用户不要用超长密码。
BCRYPT_MAX_BYTES = 72


# ============== 密码加密 ==============

def hash_password(password: str) -> str:
    """哈希密码"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(_to_bcrypt_bytes(password), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(
        _to_bcrypt_bytes(plain_password),
        hashed_password.encode(),
    )


def _to_bcrypt_bytes(password: str) -> bytes:
    """把明文压到 bcrypt 能接受的 72 字节以内（UTF-8 安全截断）"""
    raw = password.encode("utf-8")
    if len(raw) <= BCRYPT_MAX_BYTES:
        return raw
    # 逐字符累加，避免把一个多字节汉字的字节从中间切断产生乱码
    out = ""
    for ch in password:
        if len((out + ch).encode("utf-8")) > BCRYPT_MAX_BYTES:
            break
        out += ch
    return out.encode("utf-8")


# ============== JWT ==============

def _resolve_secret_key() -> str:
    """
    取 JWT 签名密钥

    优先用 .env 里的 JWT_SECRET_KEY；
    没配就退化到复用 LLM 密钥，并打一条 warning 提醒这是临时做法
    （复用业务密钥的坏处：换 LLM 密钥会导致所有登录态同时失效）。
    """
    if settings.jwt_secret_key:
        return settings.jwt_secret_key
    app_logger.warning(
        "⚠️ 未配置 JWT_SECRET_KEY，临时复用 LLM_API_KEY 作为签名密钥；"
        "上线前请在 .env 设置独立的 JWT_SECRET_KEY"
    )
    return settings.dashscope_api_key


SECRET_KEY = _resolve_secret_key()
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
