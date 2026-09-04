"""
wechat_automator 工具：自动化交互聚合。

合并所有自动化 + 运行时查询工具（13 个 action）。
含内部必填参数校验，缺失时返回结构化错误指导。
"""
import json
import asyncio
import os
import socket
import tempfile
from typing import TYPE_CHECKING

from ..core.cli import _run_cli, _resolve_project_path
from ..core.config import CLI_PATH, DEFAULT_PROJECT_PATH
from ..core.errors import ErrorCode
from ..core.node_bridge import _run_node_script, invalidate_connection
from ..models.schemas import WechatAutomatorInput
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP

# 各 action 的必填参数映射
REQUIRED_PARAMS: dict[str, list[str]] = {
    "tap":          ["selector"],
    "input":        ["selector", "value"],
    "element_info": ["selector"],
    "set_data":     ["data_json"],
    "call_method":  ["method"],
    "call_wx":      ["method"],
    "mock_wx":      ["method", "result_json"],
    # evaluate 的必填是 expression / fn_source 二选一，单独校验见 wechat_automator
}


def register_automator(mcp: "FastMCP") -> None:
    """将 wechat_automator 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_automator",
        annotations={
            "title": "自动化交互",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )(wechat_automator)


_WS_UNREACHABLE_MARK = "Failed connecting to ws://"


def _annotate_ws_failure(raw: str) -> str:
    """automator 连不上 9420 时统一附恢复提示。

    真机（2026-09-03）：项目窗口自己关掉后，所有 automator 动作只剩一句
    「Failed connecting to ws://localhost:9420 …」，agent 拿不到下一步该做什么。
    """
    try:
        payload = json.loads(raw)
    except Exception:
        return raw
    if payload.get("success") or payload.get("hint"):
        return raw
    if _WS_UNREACHABLE_MARK not in str(payload.get("message", "")):
        return raw
    payload["hint"] = (
        "automator 端口未监听：项目窗口可能已关闭，或自动化未开启。"
        "先 wechat_automator(action='start')；仍失败用 wechat_ide(action='open', cdp_enabled=True) "
        "重开项目后再 start。"
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def wechat_automator(params: WechatAutomatorInput) -> str:
    """小程序自动化交互与运行时查询。
    支持 action: start(开启自动化), tap(点击), input(输入),
    element_info(元素信息), set_data(设置数据), call_method(调用方法),
    call_wx(调用wx API), mock_wx(Mock wx), evaluate(执行JS),
    page_stack(页面栈), page_data(页面数据), system_info(系统信息),
    storage(缓存)。
    返回 JSON: {success, data, message, error_code?}。
    """
    # 必填参数校验
    missing = [
        p for p in REQUIRED_PARAMS.get(params.action, [])
        if getattr(params, p) is None
    ]
    if missing:
        return _fail(
            ErrorCode.PARAM_MISSING,
            f"action='{params.action}' 缺少必填参数: {', '.join(missing)}",
            hint=f"请提供以下参数：{', '.join(missing)}",
        )
    if params.action == "evaluate" and params.expression is None and params.fn_source is None:
        return _fail(
            ErrorCode.PARAM_MISSING,
            "action='evaluate' 缺少必填参数: expression 或 fn_source（二选一）",
            hint=(
                "推荐 fn_source：完整函数源码（如 'function(){ a(); b(); return c(); }'），"
                "支持多语句，需显式 return，入参走 args_json；单个表达式可直接用 expression。"
            ),
        )

    try:
        if params.action == "start":
            raw = await _action_start(params)
        elif params.action == "tap":
            raw = await _action_tap(params)
        elif params.action == "input":
            raw = await _action_input(params)
        elif params.action == "element_info":
            raw = await _action_element_info(params)
        elif params.action == "set_data":
            raw = await _action_set_data(params)
        elif params.action == "call_method":
            raw = await _action_call_method(params)
        elif params.action == "call_wx":
            raw = await _action_call_wx(params)
        elif params.action == "mock_wx":
            raw = await _action_mock_wx(params)
        elif params.action == "evaluate":
            raw = await _action_evaluate(params)
        elif params.action == "page_stack":
            raw = await _action_page_stack(params)
        elif params.action == "page_data":
            raw = await _action_page_data(params)
        elif params.action == "system_info":
            raw = await _action_system_info(params)
        elif params.action == "storage":
            raw = await _action_storage(params)
        else:
            return _fail(ErrorCode.UNKNOWN_ERROR, f"未知 action: {params.action}")
        return _annotate_ws_failure(raw)
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")


async def _verify_port_ready(port: int, max_attempts: int = 20, interval: float = 1.0) -> bool:
    """轮询检测端口是否可连接（TCP 层）。"""
    for _ in range(max_attempts):
        try:
            s = socket.create_connection(("localhost", port), timeout=1)
            s.close()
            return True
        except (ConnectionRefusedError, OSError, TimeoutError):
            await asyncio.sleep(interval)
    return False


async def _verify_ws_ready(port: int) -> bool:
    """通过 daemon 做 WS 级握手验证（pageStack 查询）。

    TCP 可连接不代表 miniprogram-automator 的 WebSocket 握手完成，
    需要真实发一次请求才能确认。复用 daemon 已有的 1s 重试和 3s 超时保护。

    注意：必须调用 automation.js 的 pageStack（驼峰），
    ui_debug.js 里无此 action（历史 bug，v0.9.5 已修复 build.py 同类调用）。
    """
    try:
        result = await _run_node_script(
            "automation.js", "--port", str(port), "--action", "pageStack",
            timeout=10,
        )
        return bool(result.get("success"))
    except Exception:
        return False


async def _action_start(params: WechatAutomatorInput) -> str:
    """开启自动化测试端口，做 CLI+TDP+WS 三重就绪验证。

    v0.9.8 起改用 _run_cli 同步等待 CLI 返回结果，
    替换原先 subprocess.Popen 丢弃输出的方式，CLI 失败可立即感知。
    """
    proj = params.project_path or DEFAULT_PROJECT_PATH
    if not proj:
        return _fail(ErrorCode.PROJECT_PATH_MISSING, "未提供小程序项目路径，无法开启自动化端口。")

    cli = os.environ.get("WECHAT_DEVTOOLS_CLI", CLI_PATH)

    try:
        # Step 1: 同步执行 cli.bat auto，等待返回结果
        cli_args = ["auto", "--project", proj, "--auto-port", str(params.auto_port)]
        if params.auto_account:
            cli_args.extend(["--auto-account", params.auto_account])

        # Step 1+2: cli auto → TCP 就绪。项目窗口还没加载完时 cli auto 会假成功
        # （打印 ✔ auto、退出码 0，但端口不监听）。真机（2.02.2608060）实测纯 CLI open
        # 后 3s 调 start 必失败、18s 后必成功。最多重试 3 轮，每轮间隔 3s。
        max_cli_attempts = 3
        tcp_ready = False
        cli_attempts = 0
        for cli_attempts in range(1, max_cli_attempts + 1):
            cli_result = await _run_cli(*cli_args, timeout=30)
            if not cli_result["success"]:
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    f"CLI auto 执行失败 (rc={cli_result['return_code']})",
                    hint=cli_result.get("stderr", "")[:200] or "请确认 IDE 已打开项目且服务端口已开启。",
                )
            tcp_ready = await _verify_port_ready(params.auto_port, max_attempts=5)
            if tcp_ready:
                break
            if cli_attempts < max_cli_attempts:
                await asyncio.sleep(3)
        if not tcp_ready:
            return _fail(
                ErrorCode.UNKNOWN_ERROR,
                f"CLI auto 连续 {max_cli_attempts} 次返回成功但端口 {params.auto_port} 未监听。",
                hint=(
                    "项目窗口可能尚未加载完或已关闭：稍后重试 start；"
                    "仍失败用 wechat_ide(action='open', cdp_enabled=True) 重开项目后再 start。"
                ),
            )

        # Step 3: WS 级握手验证。首次失败 → invalidate 缓存 + 2s 退避 + 再试一次。
        ws_ready = await _verify_ws_ready(params.auto_port)
        verify_attempts = 1
        if not ws_ready:
            try:
                await invalidate_connection(params.auto_port)
            except Exception:
                pass
            await asyncio.sleep(2)
            ws_ready = await _verify_ws_ready(params.auto_port)
            verify_attempts = 2

        if ws_ready:
            return _ok(
                {
                    "port": params.auto_port,
                    "verified": True,
                    "tcp_ready": True,
                    "ws_ready": True,
                    "verify_attempts": verify_attempts,
                    "cli_attempts": cli_attempts,
                },
                message=f"自动化端口 {params.auto_port} 已就绪（CLI + TCP + WS 三重验证通过）。",
            )
        return _ok(
            {
                "port": params.auto_port,
                "verified": False,
                "tcp_ready": True,
                "ws_ready": False,
                "verify_attempts": verify_attempts,
                "cli_attempts": cli_attempts,
                "retry_after_ms": 3000,
                "hint": "TCP 已监听但 WebSocket 握手未完成，可能自动化组件仍在初始化。建议等待 3 秒后重试。",
            },
            message=f"自动化端口 {params.auto_port} 的 WS 层未就绪（已尝试 {verify_attempts} 次）。",
        )
    except FileNotFoundError:
        return _fail(ErrorCode.CLI_NOT_FOUND, f"找不到微信开发者工具 CLI：{cli}")
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, str(e))


async def _action_tap(params: WechatAutomatorInput) -> str:
    result = await _run_node_script("automation.js", "--port", str(params.auto_port), "--action", "tap", "--selector", params.selector)
    if result.get("success"):
        return _ok({"selector": params.selector}, message=f"已点击元素：{params.selector}")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "点击失败"))


async def _action_input(params: WechatAutomatorInput) -> str:
    result = await _run_node_script("automation.js", "--port", str(params.auto_port), "--action", "input", "--selector", params.selector, "--value", params.value)
    if result.get("success"):
        return _ok({"selector": params.selector, "value": params.value}, message="输入成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "输入失败"))


async def _action_element_info(params: WechatAutomatorInput) -> str:
    args = ["--port", str(params.auto_port), "--action", "elementInfo", "--selector", params.selector]
    if params.style_prop:
        args.extend(["--prop", params.style_prop])
    result = await _run_node_script("automation.js", *args)
    if result.get("success"):
        return _ok({"element": result.get("element", {})}, message="获取元素信息成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "获取元素信息失败"))


async def _action_set_data(params: WechatAutomatorInput) -> str:
    result = await _run_node_script("automation.js", "--port", str(params.auto_port), "--action", "setData", "--data", params.data_json)
    if result.get("success"):
        return _ok({"path": result.get("path"), "updated_keys": result.get("updatedKeys", [])}, message="页面数据已更新。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "设置数据失败"))


async def _action_call_method(params: WechatAutomatorInput) -> str:
    args = ["--port", str(params.auto_port), "--action", "callMethod", "--method", params.method]
    if params.args_json:
        args.extend(["--args", params.args_json])
    result = await _run_node_script("automation.js", *args)
    if result.get("success"):
        return _ok({
            "method": params.method,
            "return_value": result.get("returnValue"),
            "path": result.get("path"),
        }, message=f"方法 {params.method} 调用成功。")
    page_hint = f" (当前页面: {result.get('path', 'unknown')})" if result.get("path") else ""
    return _fail(ErrorCode.UNKNOWN_ERROR, f"{result.get('error', '方法调用失败')}{page_hint}")


async def _action_call_wx(params: WechatAutomatorInput) -> str:
    args = ["--port", str(params.auto_port), "--action", "callWx", "--method", params.method]
    if params.args_json:
        args.extend(["--args", params.args_json])
    result = await _run_node_script("automation.js", *args)
    if result.get("success"):
        return _ok({"method": params.method, "return_value": result.get("returnValue")}, message=f"wx.{params.method} 调用成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "wx API 调用失败"))


async def _action_mock_wx(params: WechatAutomatorInput) -> str:
    result = await _run_node_script("automation.js", "--port", str(params.auto_port), "--action", "mockWx", "--method", params.method, "--result", params.result_json)
    if result.get("success"):
        return _ok({"method": params.method}, message=f"wx.{params.method} Mock 成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "Mock 失败"))


async def _action_evaluate(params: WechatAutomatorInput) -> str:
    """执行 JS：优先 fn_source（完整函数源码 + args_json），否则 expression 单表达式。

    daemon 回传 mode：function / expression / statement。expression 走语句模式且没有
    return 时结果必然为 null，此处附 hint 指引改用 fn_source，避免静默返回空。
    """
    args = ["--port", str(params.auto_port), "--action", "evaluate"]
    if params.fn_source is not None:
        args.extend(["--fn-source", params.fn_source])
        if params.args_json:
            args.extend(["--args", params.args_json])
    else:
        args.extend(["--code", params.expression])
    result = await _run_node_script("ui_debug.js", *args)
    if result.get("success"):
        data: dict = {"result": result.get("result")}
        mode = result.get("mode")
        if mode:
            data["mode"] = mode
        if mode == "statement" and result.get("result") is None:
            data["hint"] = (
                "表达式已按语句模式执行但未 return，结果为 null；"
                "多语句请用 fn_source 并显式 return。"
            )
        return _ok(data, message="表达式执行成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "执行失败"))


async def _action_page_stack(params: WechatAutomatorInput) -> str:
    result = await _run_node_script("automation.js", "--port", str(params.auto_port), "--action", "pageStack")
    if result.get("success"):
        return _ok({"depth": result.get("depth", 0), "pages": result.get("pages", [])}, message="获取页面栈成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "获取页面栈失败"))


async def _action_page_data(params: WechatAutomatorInput) -> str:
    args = ["--port", str(params.auto_port), "--action", "data"]
    if params.expected_path:
        args.extend(["--expected-path", params.expected_path])
    result = await _run_node_script("ui_debug.js", *args)
    if result.get("success"):
        data = {"path": result.get("path", ""), "data": result.get("data", {})}
        if result.get("path_mismatch"):
            data["path_mismatch"] = True
            data["warning"] = result.get("warning", "当前页面路径与预期不符")
        return _ok(data, message="获取页面数据成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "获取页面数据失败"))


async def _action_system_info(params: WechatAutomatorInput) -> str:
    system_info_script = """module.exports = async function(miniProgram) {
  const info = await miniProgram.systemInfo();
  return info;
};"""
    tmp_path = os.path.join(tempfile.gettempdir(), "wechat_mcp_sysinfo.js")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(system_info_script)
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"写入临时脚本失败: {e}")

    result = await _run_node_script("run_test_script.js", "--port", str(params.auto_port), "--script", tmp_path, "--timeout", "15", timeout=30)
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    if result.get("success"):
        return _ok({"system_info": result.get("script_result", {})}, message="获取系统信息成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "获取系统信息失败"))


async def _action_storage(params: WechatAutomatorInput) -> str:
    args = ["--port", str(params.auto_port), "--action", "storage"]
    if params.key:
        args.extend(["--key", params.key])
    result = await _run_node_script("ui_debug.js", *args)
    if result.get("success"):
        if params.key:
            return _ok({"key": params.key, "value": result.get("value")}, message=f"Storage key '{params.key}' 获取成功。")
        return _ok({
            "keys": result.get("keys", []),
            "current_size": result.get("currentSize"),
            "limit_size": result.get("limitSize"),
        }, message="Storage 信息获取成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("error", "获取 Storage 失败"))
