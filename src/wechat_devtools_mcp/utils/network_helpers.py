"""CDP Network 事件的合并、过滤和敏感字段脱敏。"""
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|token|secret|password|openid|session)", re.IGNORECASE
)
_MAX_POST_DATA_BYTES = 64 * 1024


def _mask_value(key: str, value: Any) -> Any:
    return "***" if _SENSITIVE_KEY.search(key) else value


def _redact_url(url: str) -> tuple[str, dict[str, str]]:
    """脱敏 URL query，同时保留供调用方断言的 query 参数。"""
    try:
        parsed = urlsplit(url)
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        query = {key: str(_mask_value(key, value)) for key, value in query_pairs}
        safe_query = urlencode(
            [(key, _mask_value(key, value)) for key, value in query_pairs],
            doseq=True,
        )
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, safe_query, parsed.fragment)), query
    except (TypeError, ValueError):
        return url, {}


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _mask_value(key, _redact_json(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


def _redact_post_data(post_data: str | None) -> tuple[str | None, bool]:
    if post_data is None:
        return None, False
    truncated = len(post_data.encode("utf-8")) > _MAX_POST_DATA_BYTES
    if truncated:
        post_data = post_data.encode("utf-8")[:_MAX_POST_DATA_BYTES].decode("utf-8", errors="ignore")
    try:
        return json.dumps(_redact_json(json.loads(post_data)), ensure_ascii=False, separators=(",", ":")), truncated
    except (TypeError, ValueError, json.JSONDecodeError):
        pairs = parse_qsl(post_data, keep_blank_values=True)
        if pairs:
            return urlencode([(key, _mask_value(key, value)) for key, value in pairs]), truncated
        return post_data, truncated


def _format_network_requests(
    raw_events: list[dict[str, Any]],
    url_pattern: str | None,
    include_post_data: bool,
    include_responses: bool,
    max_requests: int,
) -> dict[str, Any]:
    """按 requestId 合并事件，过滤 URL，并返回供 MCP 使用的结构化记录。"""
    try:
        pattern = re.compile(url_pattern) if url_pattern else None
    except re.error as exc:
        raise ValueError(f"url_pattern 无效：{exc}") from exc

    requests: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        content = event.get("content")
        if not isinstance(content, dict):
            continue
        request_id = content.get("requestId")
        if not isinstance(request_id, str):
            continue
        event_type = event.get("type")
        if event_type == "REQUEST":
            raw_url = content.get("url")
            if not isinstance(raw_url, str):
                continue
            safe_url, query = _redact_url(raw_url)
            requests[request_id] = {
                "request_id": request_id,
                "url": safe_url,
                "method": content.get("method"),
                "query": query,
                "timestamp": event.get("timestamp", ""),
                "target_type": event.get("targetType", ""),
                "target_hint": event.get("targetHint", "other"),
                "_post_data": content.get("postData"),
            }
            order.append(request_id)
        elif request_id in requests:
            request = requests[request_id]
            if event_type == "RESPONSE":
                request["_status"] = content.get("status")
                request["_mime_type"] = content.get("mimeType")
            elif event_type == "FINISHED":
                request["encoded_data_length"] = content.get("encodedDataLength")
            elif event_type == "FAILED":
                request["error_text"] = content.get("errorText")
                request["canceled"] = content.get("canceled")
                if content.get("blockedReason"):
                    request["blocked_reason"] = content["blockedReason"]

    matched_requests: list[dict[str, Any]] = []
    failed = 0
    for request_id in order:
        request = requests[request_id]
        matched = pattern.search(request["url"]) is not None if pattern else True
        if not matched:
            continue
        request["matched"] = True
        if include_post_data:
            post_data, truncated = _redact_post_data(request.pop("_post_data", None))
            request["post_data"] = post_data
            if truncated:
                request["post_data_truncated"] = True
        else:
            request.pop("_post_data", None)
        if include_responses:
            request["status"] = request.pop("_status", None)
            request["mime_type"] = request.pop("_mime_type", None)
        else:
            request.pop("_status", None)
            request.pop("_mime_type", None)
        if request.get("error_text"):
            failed += 1
        matched_requests.append(request)

    truncated = len(matched_requests) > max_requests
    displayed = matched_requests[:max_requests]
    return {
        "summary": {
            "total": len(order),
            "matched": len(matched_requests),
            "failed": failed,
            "truncated": truncated,
        },
        "requests": displayed,
        "url_pattern": url_pattern,
    }
