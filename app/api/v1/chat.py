"""
流式对话 API（SSE）
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.handoffs.travel_agent import create_travel_agent
from app.api.dependencies import get_current_user
from app.models.base import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate
from app.utils.rate_limit import enforce_chat_limit
from app.utils.logger import app_logger


router = APIRouter(prefix="/chat", tags=["对话"])


async def save_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    extra_info: dict | None = None,
) -> Message:
    """保存消息到数据库"""

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        extra_info=extra_info or {},
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    return message


def sse(data: dict) -> str:
    """SSE 标准 data 帧"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def generate_sse_stream(
    conversation_id: uuid.UUID,
    user_message: str,
    db: AsyncSession,
    user: User,
):
    """生成 SSE 流式响应"""

    assistant_message = ""
    error_message = None

    try:
        # 1. 保存用户消息
        await save_message(db, conversation_id, "user", user_message)

        # 2. 创建 Agent
        agent = await create_travel_agent()

        # 3. LangGraph StateGraph 需要字典格式的状态更新
        input_data = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": str(user.id),
        }

        # 4. 使用 astream_events 获取更细粒度的流式输出
        agent_iter = agent.astream_events(
            input_data,
            config={
                "configurable": {
                    "thread_id": str(conversation_id),
                }
            },
            version="v2",
        )

        while True:
            try:
                event = await asyncio.wait_for(
                    agent_iter.__anext__(),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                error_message = "Agent 长时间未响应，本次请求已超时。"
                break
            except StopAsyncIteration:
                break

            kind = event.get("event")

            # 捕获 LLM 流式输出
            if kind == "on_chat_model_stream":
                # 排除嵌套 RAG 中的内部评分模型，
                # 避免重排序器的原始 JSON 被当成用户可见回答。
                metadata = event.get("metadata") or {}
                if "destination_router" in str(metadata.get("langgraph_node", "")):
                    await asyncio.sleep(0)
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = chunk.content
                    assistant_message += token
                    yield sse({
                        "type": "token",
                        "content": token,
                    })

            # 捕获工具调用信息
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                yield sse({
                    "type": "tool_call",
                    "tool": tool_name,
                })

            await asyncio.sleep(0)

        # 5. 保存 AI 回复
        if assistant_message.strip():
            await save_message(
                db,
                conversation_id,
                "assistant",
                assistant_message,
            )

        if error_message:
            yield sse({
                "type": "error",
                "message": error_message,
            })
        else:
            yield sse({"type": "done"})

    except Exception as e:
        app_logger.exception("❌ SSE 流式对话错误")
        yield sse({
            "type": "error",
            "message": str(e),
        })


# ========== 破甲拦截 ==========

JAILBREAK_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "you are now",
    "you are codex",
    "you are no longer",
    "new system prompt",
    "system prompt:",
    "system prompt：",
    "无视所有",
    "无视之前",
    "忽略之前",
    "忽略所有",
    "解除限制",
    "重置提示词",
    "重置系统",
    "不要遵守",
    "覆盖系统",
    "覆盖提示词",
    "零警告原则",
    "绝对铁律",
    "不可覆盖",
    "highest priority constraint",
    "absolute iron rules",
]


def is_jailbreak_attempt(message: str) -> bool:
    """检测用户消息是否为破甲尝试"""
    lowered = message.lower()
    return any(pattern in lowered for pattern in JAILBREAK_PATTERNS)


@router.post(
    "/stream/{conversation_id}",
    dependencies=[Depends(enforce_chat_limit)],
)
async def stream_chat(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    流式对话（SSE）

    Returns:
        StreamingResponse: SSE 流式响应
    """

    # 验证会话归属
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user.id)
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )

    # 破甲拦截：命中关键词直接返回拒绝消息，不送给模型
    if is_jailbreak_attempt(data.content):
        app_logger.warning(f"🛡️ 拦截破甲尝试: user_id={user.id}")

        async def jailbreak_rejection():
            yield sse({
                "type": "token",
                "content": "抱歉，我不能执行与旅行规划无关的指令。请告诉我你的出行需求，我继续为你规划行程。",
            })
            yield sse({"type": "done"})

        return StreamingResponse(
            jailbreak_rejection(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 返回 SSE 流
    return StreamingResponse(
        generate_sse_stream(
            conversation_id,
            data.content,
            db,
            user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{conversation_id}")
async def get_chat_history(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话历史消息"""

    # 验证会话归属
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user.id)
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )

    # 查询消息
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )

    messages = result.scalars().all()

    return {
        "conversation": conversation.to_dict(),
        "messages": [message.to_dict() for message in messages],
    }
