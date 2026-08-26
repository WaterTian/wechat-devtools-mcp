"""
CDP 日志过滤与结构化格式化辅助函数（v2 实现）。
"""
import json
import re
from typing import Any

# 系统日志过滤模式（非业务日志）
SYSTEM_LOG_PATTERNS: list[str] = [
    r"\[system\]",
    r"WAService\.js",
    r"WAWebview\.js",
    r"__dev__",
    # IDE 2.x(Electron) 的外壳页 file:///…/app.asar/html/electron-*.html。
    # 实测占总采集量六成，cdp_core 已在连接层排除，这里作为兜底
    # （用户可能还在用未重建的旧 bundle）。
    r"app\.asar/html/electron-",
]

# 启动阶段噪音模式（仅 filter_startup_noise=True 时生效）
STARTUP_NOISE_PATTERNS: list[str] = [
    r"__route__",
    r"ide:///extensions/",
    r"devtools://",
]

# WXML 错误保护模式（匹配时不被噪音过滤吞掉）
WXML_ERROR_PATTERNS: list[str] = [
    r"\.wxml",
    r"Bad attr",
    r"WXML Runtime",
    r"template not found",
]


def _is_wxml_error(message: str, source: str) -> bool:
    """检查消息或来源是否包含 WXML 编译错误特征。"""
    text = f"{message} {source}"
    return any(re.search(p, text) for p in WXML_ERROR_PATTERNS)


def _classify_cdp_log(log: dict[str, Any]) -> tuple[str, str, str]:
    """将单条 CDP 原始日志分类为 (level, message, source)。

    Args:
        log: CDP 原始日志字典，含 type、url、content 字段。

    Returns:
        tuple[str, str, str]: (level, message, source)，level 为 error/warning/info。
    """
    log_type = log.get("type", "UNKNOWN")
    url = log.get("url", "")
    content = log.get("content", {})

    text = ""
    level = "info"
    source = ""

    if log_type in ("RUNTIME_CONSOLE", "Runtime.consoleAPICalled"):
        if isinstance(content, dict) and "args" in content:
            text = " ".join(
                str(a.get("value") if isinstance(a, dict) else a)
                for a in content["args"]
            )
            raw_level = content.get("type", "log")
            if raw_level in ("error", "exception"):
                level = "error"
            elif raw_level in ("warning", "warn"):
                level = "warning"
            else:
                level = "info"
    elif log_type == "ASSERT":
        # console.assert 失败 → 降级为 warning（通常是框架内部断言）
        if isinstance(content, dict) and "args" in content:
            text = " ".join(
                str(a.get("value") if isinstance(a, dict) else a)
                for a in content["args"]
            )
        level = "warning"
    elif log_type in ("CONSOLE", "Console.messageAdded"):
        msg_body = content if isinstance(content, dict) else {}
        text = msg_body.get("text", "")
        raw_level = msg_body.get("level", "log")
        if raw_level in ("error", "exception"):
            level = "error"
        elif raw_level in ("warning", "warn"):
            level = "warning"
        else:
            level = "info"
        source = msg_body.get("url", "")
    elif log_type == "LOG_ENTRY":
        # Log.entryAdded 事件（WXML 编译错误等结构化日志）
        entry = content if isinstance(content, dict) else {}
        text = entry.get("text", "")
        raw_level = entry.get("level", "info")
        if raw_level in ("error", "severe"):
            level = "error"
        elif raw_level in ("warning", "warn"):
            level = "warning"
        else:
            level = "info"
        source = entry.get("url", "")
    elif log_type == "EXCEPTION":
        if isinstance(content, dict):
            text = content.get("exception", {}).get("description", "Unknown Exception")
        level = "error"

    if not source and url:
        # 从 URL 提取可读来源
        if not url.startswith(("ide://", "devtools://")):
            if "__pageframe__/" in url:
                # 渲染层：还原为页面路径，如 pages/home/index
                source = url.split("__pageframe__/")[-1].split("?")[0]
            elif "/appservice/" in url:
                # 逻辑层：1.x 是 /appservice/mainframe，2.x 是
                # /appservice/s0/_sessionId/<session>/mainframe，归一化为统一标识
                source = "appservice"
            else:
                source = url.split("/")[-1].split("?")[0]

    # 清理样式标记
    if text.startswith("%c"):
        text = text.replace("%c", "", 1)
        text = text.replace(" font-weight: bold;", "")

    return level, text.strip(), source


def _format_cdp_logs_v2(
    raw_logs: list[dict[str, Any]],
    detail_level: str = "concise",
    max_logs: int = 50,
    filter_startup_noise: bool = False,
) -> dict[str, Any]:
    """将 CDP 原始日志列表转换为结构化输出。

    Args:
        raw_logs: CDP 原始日志列表。
        detail_level: "concise"（仅 summary + errors/warnings）或 "full"（全量）。
        max_logs: 最大返回条数，超出时截断并标注 truncated=true。
        filter_startup_noise: 是否过滤启动阶段噪音（__route__、ide:///extensions/、devtools://）。

    Returns:
        dict: {summary: {...}, logs: [...]}。
    """
    classified: dict[str, list[dict[str, Any]]] = {"error": [], "warning": [], "info": []}
    seen: set[str] = set()

    for log in raw_logs:
        # 过滤系统日志
        log_text = json.dumps(log, ensure_ascii=False) if isinstance(log, dict) else str(log)
        if any(re.search(p, log_text) for p in SYSTEM_LOG_PATTERNS):
            continue

        level, message, source = _classify_cdp_log(log)
        if not message:
            continue

        # 启动噪音过滤（WXML 错误保护优先）
        if filter_startup_noise and not _is_wxml_error(message, source):
            if any(re.search(p, log_text) for p in STARTUP_NOISE_PATTERNS):
                continue

        msg_key = f"{level}:{message}"
        if msg_key in seen:
            continue
        seen.add(msg_key)

        log_entry: dict[str, Any] = {
            "level": level,
            "message": message,
            "source": source,
            "timestamp": log.get("timestamp", "") if isinstance(log, dict) else "",
        }
        # [object Object] 残留提示
        if "[object Object]" in message:
            log_entry["hint"] = "对象未完整序列化，建议使用 wechat_automator(action='evaluate') 直接调用 API 获取完整返回值。"
        classified[level].append(log_entry)

    # 按优先级合并：error > warning > info
    all_logs = classified["error"] + classified["warning"] + classified["info"]
    truncated = len(all_logs) > max_logs
    all_logs = all_logs[:max_logs]

    summary: dict[str, Any] = {
        "total": len(all_logs),
        "errors": len(classified["error"]),
        "warnings": len(classified["warning"]),
        "info": len(classified["info"]),
        "truncated": truncated,
    }

    # concise 模式只保留 errors 和 warnings
    if detail_level == "concise":
        display_logs = [log for log in all_logs if log["level"] in ("error", "warning")]
    else:
        display_logs = all_logs

    return {"summary": summary, "logs": display_logs}
