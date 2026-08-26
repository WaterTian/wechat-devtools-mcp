"""
错误码枚举与统一错误响应构造器。
"""
import json
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """机器可读的错误码枚举，继承 str 以便 JSON 序列化。"""
    CLI_TIMEOUT          = "CLI_TIMEOUT"
    CLI_NOT_FOUND        = "CLI_NOT_FOUND"
    NODE_NOT_FOUND       = "NODE_NOT_FOUND"
    PROJECT_PATH_MISSING = "PROJECT_PATH_MISSING"
    PARAM_MISSING        = "PARAM_MISSING"
    UNKNOWN_ERROR        = "UNKNOWN_ERROR"


def _make_error(error_code: ErrorCode, message: str, hint: str = "") -> str:
    """构造结构化错误响应 JSON 字符串。

    Args:
        error_code: ErrorCode 枚举值，机器可读的错误标识符。
        message: 人类可读的错误描述（中文）。
        hint: 可选的修复建议。

    Returns:
        JSON 字符串，{success: false, error_code, message[, hint]}。
    """
    payload: dict[str, Any] = {
        "success": False,
        "error_code": error_code.value,
        "message": message,
    }
    if hint:
        payload["hint"] = hint
    return json.dumps(payload, ensure_ascii=False, indent=2)
