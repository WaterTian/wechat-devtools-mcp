"""
统一返回值构造器：所有工具统一使用 _ok()/_fail() 返回 JSON 信封。
"""
import json
from typing import Any

from ..core.errors import ErrorCode


def _ok(data: dict[str, Any], message: str = "") -> str:
    """构造成功响应 JSON 字符串。

    Args:
        data: 响应数据字典。
        message: 可选的人类可读描述。

    Returns:
        JSON 字符串：{success: true, data, message}。
    """
    return json.dumps(
        {"success": True, "data": data, "message": message},
        ensure_ascii=False,
        indent=2,
    )


def _fail(
    error_code: ErrorCode,
    message: str,
    hint: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """构造失败响应 JSON 字符串。

    Args:
        error_code: ErrorCode 枚举值。
        message: 人类可读的错误描述。
        hint: 可选的修复建议。
        extra: 可选的附加数据，会合并到顶层返回中。

    Returns:
        JSON 字符串：{success: false, error_code, message[, hint][, ...extra]}。
    """
    payload: dict[str, Any] = {
        "success": False,
        "error_code": error_code.value,
        "message": message,
    }
    if hint:
        payload["hint"] = hint
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, indent=2)
