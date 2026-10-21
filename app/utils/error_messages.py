"""
校验错误中文化

作用：
    FastAPI 对请求体校验失败（HTTP 422）默认返回 Pydantic 的英文错误数组，
    形如 {"detail":[{"type":"string_too_short","loc":["body","password"], ...}]}。
    这个结构是数组不是字符串，前端如果直接把它当文案显示，
    JavaScript 会把它转成 "[object Object]"，用户完全看不到原因。

    这里统一翻译成人话，并输出项目约定的错误结构
    {"code": 422, "msg": "...", "data": null}。
"""

from typing import Any


# 字段英文名 -> 用户能看懂的中文名
FIELD_ZH: dict[str, str] = {
    "username": "用户名",
    "email": "邮箱",
    "password": "密码",
    "content": "消息内容",
    "title": "会话名称",
    "status": "状态",
    "body": "提交内容",
    "query": "查询参数",
    "path": "地址参数",
    "conversation_id": "会话 ID",
}

# Pydantic v2 的 error type -> 中文模板
# 模板里可用 {field} / {min_length} / {max_length} / {msg}
TYPE_ZH: dict[str, str] = {
    "missing": "{field}不能为空",
    "string_too_short": "{field}太短了，至少需要 {min_length} 个字符",
    "string_too_long": "{field}太长了，最多 {max_length} 个字符",
    "too_short": "{field}数量太少，至少需要 {min_length} 项",
    "too_long": "{field}数量太多，最多 {max_length} 项",
    "value_error.email": "邮箱格式不正确，请检查是否有 @ 和域名",
    "value_error": "{field}格式不正确",
    "string_pattern_mismatch": "{field}格式不符合要求",
    "int_parsing": "{field}必须是整数",
    "float_parsing": "{field}必须是数字",
    "json_invalid": "请求体不是合法的 JSON",
    "model_attributes_type": "{field}格式不正确",
    "extra_forbidden": "{field}是不允许的字段",
}


def _field_label(loc: Any) -> str:
    """从 loc 数组里挑出最后一个有意义的字段名并翻译"""
    if not loc:
        return "提交内容"
    # loc 形如 ["body", "password"]，取最后一段
    raw = loc[-1] if isinstance(loc, (list, tuple)) else loc
    key = str(raw)
    # 数字下标（列表元素）不作字段名，往上找一层
    if key.isdigit():
        for item in reversed(list(loc)):
            if not str(item).isdigit():
                key = str(item)
                break
    return FIELD_ZH.get(key, key)


def _one_message(err: dict) -> str:
    """把单条校验错误翻译成中文"""
    etype = str(err.get("type", ""))
    field = _field_label(err.get("loc"))
    template = TYPE_ZH.get(etype)

    if template is None:
        # 未知类型：用字段名 + 原始 msg，至少不是 [object Object]
        raw_msg = str(err.get("msg", "")).strip()
        return f"{field}填写有误" + (f"（{raw_msg}）" if raw_msg else "")

    ctx = err.get("ctx") or {}
    return template.format(
        field=field,
        min_length=ctx.get("min_length", err.get("min_length", "")),
        max_length=ctx.get("max_length", err.get("max_length", "")),
        msg=err.get("msg", ""),
    )


def friendly_validation_message(errors: list) -> str:
    """
    把 FastAPI 的校验错误列表压成一句人话

    多条错误只报第一条，避免 toast 弹出一长串；
    其余条数用「等 N 处」提示，前端不用二次解析。
    """
    if not errors:
        return "提交的内容有格式问题"

    first = _one_message(errors[0])
    if len(errors) == 1:
        return first
    return f"{first}（另有 {len(errors) - 1} 处需要修改）"
