"""
wechat_inspector 工具：运行时日志采集。

合并原 wechat_get_console_logs、wechat_get_cdp_logs，
含 CDP v2 结构化输出（detail_level、max_logs）。
"""
from typing import TYPE_CHECKING

from ..core.errors import ErrorCode
from ..core.node_bridge import _run_node_script
from ..models.schemas import WechatInspectorInput
from ..utils.cdp_helpers import _format_cdp_logs_v2
from ..utils.network_helpers import _format_network_requests
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP


def register_inspector(mcp: "FastMCP") -> None:
    """将 wechat_inspector 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_inspector",
        annotations={
            "title": "运行时日志采集",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_inspector)


async def wechat_inspector(params: WechatInspectorInput) -> str:
    """采集小程序运行时日志和异常。
    支持 action: console(automator端口采集console日志和JS异常),
    cdp(通过CDP协议采集WXML警告、渲染层报错、废弃API提示等底层日志),
    network(通过 CDP Network.enable 采集 wx.request)。
    cdp action 需先以 cdp_enabled=true 打开项目，确保端口 9222 可用。
    返回 JSON: {success, data: {logs, summary}, message}。
    """
    try:
        if params.action == "console":
            return await _action_console(params)
        elif params.action == "cdp":
            return await _action_cdp(params)
        elif params.action == "network":
            return await _action_network(params)
        return _fail(ErrorCode.UNKNOWN_ERROR, f"未知 action: {params.action}")
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")


async def _action_console(params: WechatInspectorInput) -> str:
    """通过 automator 端口采集 console 日志和 JS 异常。"""
    script_args = [
        "--port", str(params.auto_port),
        "--duration", str(params.duration),
        "--type", params.log_type or "all",
    ]
    if params.tap_selector:
        script_args.extend(["--tap", params.tap_selector])
        script_args.extend(["--tap-delay", str(params.tap_delay)])

    result = await _run_node_script(
        "console_listener.js",
        *script_args,
        timeout=params.duration + 15,
    )

    if not result.get("success") and "error" in result:
        return _fail(
            ErrorCode.UNKNOWN_ERROR,
            f"连接失败：{result['error']}",
            hint="请确认已调用 wechat_automator(action='start') 开启了自动化端口。",
        )

    summary = result.get("summary", {})
    console_logs = result.get("console_logs", [])
    exceptions = result.get("exceptions", [])

    data = {
        "summary": {
            "total": summary.get("total_logs", 0),
            "errors": summary.get("errors", 0),
            "warnings": summary.get("warnings", 0),
            "exceptions": summary.get("exceptions", 0),
        },
        "console_logs": console_logs,
        "exceptions": exceptions,
        "port": result.get("port", params.auto_port),
        "duration": result.get("duration", params.duration),
    }

    # #21: 监听器在连接建立后才注册，短 duration 易漏捕注册前已触发的异常。
    if params.log_type in ("all", "exception") and params.duration < 6:
        data["duration_warning"] = (
            f"duration={params.duration}s 可能漏捕异常：事件监听器在 daemon 建立连接后才注册，"
            "注册前触发的 exception 无法采集。建议排查 JS 异常时使用 ≥8s。"
        )

    msg = (
        f"采集 {params.duration} 秒，共 {summary.get('total_logs', 0)} 条日志，"
        f"{len(exceptions)} 个异常。"
    )
    return _ok(data, message=msg)


async def _action_cdp(params: WechatInspectorInput) -> str:
    """通过 CDP 协议采集底层日志（WXML 警告、渲染层报错等）。"""
    # cdp_listener.js 的兼容位置参数：argv[2]=duration, argv[3]=cdp_port。
    # 早期只传了 duration，导致 schema 暴露的 cdp_port 形同虚设（永远连 9222）。
    result = await _run_node_script(
        "cdp_listener.js",
        str(params.duration),
        str(params.cdp_port),
        timeout=params.duration + 10,
    )

    # cdp_listener.js 的 handle 直接返回日志数组，daemon 把它包成
    # {"success": True, "data": [...]}。这里必须读 data —— 早期只读 logs，
    # 而该 key 根本不存在，导致 cdp 采集恒返回 0 条（ide.py / build.py 读的都是 data）。
    if isinstance(result, list):
        raw_logs = result
    elif isinstance(result, dict):
        if not result.get("success") and "error" in result:
            return _fail(
                ErrorCode.UNKNOWN_ERROR,
                f"CDP 采集失败：{result['error']}",
                hint=(
                    f"请确认已用 cdp_enabled=true 打开项目，且端口 {params.cdp_port} 未被占用"
                    "（可用 curl 127.0.0.1:<port>/json/version 确认端口上是谁）。"
                ),
            )
        raw_logs = result.get("data") or result.get("logs") or []
        if not isinstance(raw_logs, list):
            raw_logs = []
    else:
        raw_logs = []

    formatted = _format_cdp_logs_v2(raw_logs, params.detail_level, params.max_logs)

    error_cnt = formatted["summary"]["errors"]
    warn_cnt = formatted["summary"]["warnings"]
    msg = f"采集 {params.duration} 秒，发现 {error_cnt} 个错误、{warn_cnt} 个警告。"

    return _ok(formatted, message=msg)


async def _action_network(params: WechatInspectorInput) -> str:
    """通过 CDP Network.enable 采集小程序逻辑层网络请求。"""
    result = await _run_node_script(
        "network_listener.js",
        "--duration", str(params.duration),
        "--cdp-port", str(params.cdp_port),
        "--appservice-only", str(params.appservice_only).lower(),
        timeout=params.duration + 10,
    )
    if isinstance(result, dict) and not result.get("success", True):
        payload = result.get("data") if isinstance(result.get("data"), dict) else result
        code = payload.get("code")
        if code == "CDP_UNAVAILABLE":
            return _fail(
                ErrorCode.CDP_UNAVAILABLE,
                f"CDP 采集不可用：{payload.get('error', '调试端口无响应')}",
                hint=f"请确认已用 cdp_enabled=true 打开项目，且端口 {params.cdp_port} 可用。",
            )
        if code == "NETWORK_DOMAIN_UNSUPPORTED":
            return _fail(
                ErrorCode.NETWORK_DOMAIN_UNSUPPORTED,
                f"当前 CDP target 不支持 Network 域：{payload.get('error', '')}",
            )
        return _fail(ErrorCode.UNKNOWN_ERROR, f"Network 采集失败：{payload.get('error', result)}")

    payload = result.get("data") if isinstance(result, dict) else result
    if not isinstance(payload, dict):
        payload = {}
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raw_events = []
    try:
        formatted = _format_network_requests(
            raw_events, params.url_pattern, params.include_post_data,
            params.include_responses, params.max_requests,
        )
    except ValueError as exc:
        return _fail(ErrorCode.PARAM_MISSING, str(exc))

    formatted["summary"]["cdp_available"] = True
    formatted["summary"]["network_enabled_targets"] = payload.get("network_enabled_targets", 0)
    formatted["duration"] = params.duration
    formatted["cdp_port"] = params.cdp_port
    summary = formatted["summary"]
    return _ok(
        formatted,
        message=(
            f"采集 {params.duration} 秒，共 {summary['total']} 条请求，"
            f"匹配 {summary['matched']} 条。"
        ),
    )
