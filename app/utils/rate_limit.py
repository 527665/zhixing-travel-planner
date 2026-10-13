"""
接口限流（内存滑动窗口）

作用：
    给"会花钱"的接口加上调用次数上限，防止别人拿脚本狂 POST，
    把 LLM 与 MCP 的付费额度烧光。

为什么先用内存版：
    计数放在单个 FastAPI 进程的字典里，本机单进程部署完全够用。
    将来要开多进程 / 多机部署时，把 SlidingWindowRateLimiter 的存储换成
    Redis 即可，调用方代码一行不用改。
"""

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Depends, HTTPException, Request, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.utils.logger import app_logger


# ============== 核心：滑动窗口计数器 ==============

class SlidingWindowRateLimiter:
    """
    滑动窗口限流器

    原理（大白话）：
        每个 key（例如某个 IP）配一个"最近时间戳队列"。
        每次请求进来做三件事：
          1. 把落在窗口之外的旧时间戳从队头扔掉；
          2. 数一下队列里还剩几条，达到上限就拒绝；
          3. 没达到上限就把当前时间戳追加到队尾，放行。
        比"固定窗口"（每分钟清零）强的地方：
        不会出现"第 59 秒打满 + 第 61 秒又打满"的两倍突刺。
    """

    def __init__(self, limit: int, window_seconds: int, name: str = "default"):
        """
        Args:
            limit: 窗口内最多允许多少次请求
            window_seconds: 窗口长度（秒）
            name: 日志标识，方便看是哪条规则拦的
        """
        self.limit = limit
        self.window = window_seconds
        self.name = name
        # key -> 该 key 在窗口内的请求时间戳队列
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        # 上次清理过期 key 的时间，防止字典无限膨胀
        self._last_gc = time.monotonic()

    def _gc(self, now: float) -> None:
        """清理长时间没访问的 key，避免内存泄漏"""
        if now - self._last_gc < self.window * 2:
            return
        cutoff = now - self.window
        dead_keys = [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]
        for key in dead_keys:
            self._hits.pop(key, None)
        self._last_gc = now

    def allow(self, key: str) -> bool:
        """判断该 key 本次请求是否放行"""
        now = time.monotonic()
        self._gc(now)

        bucket = self._hits[key]
        cutoff = now - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            app_logger.warning(
                f"🚫 限流拦截[{self.name}] key={key} 上限={self.limit}/{self.window}s"
            )
            return False

        bucket.append(now)
        return True

    def retry_after(self, key: str) -> int:
        """距离释放一个配额还有多少秒，用于 Retry-After 响应头"""
        bucket = self._hits.get(key)
        if not bucket:
            return 1
        oldest = bucket[0]
        return max(1, int(self.window - (time.monotonic() - oldest)) + 1)


# ============== 请求身份提取 ==============

def get_client_ip(request: Request) -> str:
    """
    取客户端 IP

    优先级：
        X-Forwarded-For（前面挂了 nginx / 云负载均衡时由代理写入）的第一个地址
        -> 直连 socket 地址

    注意：
        X-Forwarded-For 是客户端可伪造的头，只有可信代理链后才该信它；
        直接暴露到公网时，限流按 IP 只是提高成本，不是绝对防线。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    client = request.client
    return client.host if client else "unknown"


# ============== 限流规则表（唯一调参入口）==============
# 想改阈值只改这里，不用碰业务代码。

RATE_RULES: dict[str, tuple[int, int]] = {
    # 注册：同 IP 每小时 5 次，挡批量注册
    "register": (5, 3600),
    # 登录：同 IP 每分钟 10 次，挡撞库
    "login": (10, 60),
    # 流式对话：同 IP 每小时 300 次，挡匿名洪水
    "chat_ip": (300, 3600),
    # 流式对话：同用户每分钟 8 次，真正防烧钱
    "chat_user_minute": (8, 60),
    # 流式对话：同用户每小时 120 次，防"每分钟歇一下再刷"
    "chat_user_hour": (120, 3600),
}

_LIMITERS: dict[str, SlidingWindowRateLimiter] = {
    rule_name: SlidingWindowRateLimiter(
        limit=limit,
        window_seconds=window,
        name=rule_name,
    )
    for rule_name, (limit, window) in RATE_RULES.items()
}


def _check(rule_name: str, identity: str) -> None:
    """超过上限抛 429"""
    limiter = _LIMITERS[rule_name]
    if not limiter.allow(identity):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="对话速度过快，请稍等一会",
            headers={"Retry-After": str(limiter.retry_after(identity))},
        )


# ============== 依赖注入入口（给路由用）==============

def enforce_register_limit(request: Request) -> None:
    """注册接口限流：按 IP"""
    _check("register", f"ip:{get_client_ip(request)}")


def enforce_login_limit(request: Request) -> None:
    """登录接口限流：按 IP"""
    _check("login", f"ip:{get_client_ip(request)}")


def enforce_chat_limit(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    """
    对话接口限流：先按用户，再按 IP

    顺序说明：
        用户维度先判，因为烧钱是按人头算的；
        IP 维度兜底，防止批量注册后轮换账号。

    说明：
        这里复用了 get_current_user，FastAPI 同一请求内会缓存依赖结果，
        不会多查一次数据库。
    """
    _check("chat_user_minute", f"user:{user.id}")
    _check("chat_user_hour", f"user:{user.id}")
    _check("chat_ip", f"ip:{get_client_ip(request)}")
