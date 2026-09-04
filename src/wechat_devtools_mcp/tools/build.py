"""
wechat_build 工具：构建与发布。

合并原 wechat_compile_check、wechat_preview、wechat_upload、
wechat_build_npm、wechat_cache_clean。
"""
import asyncio
import json
import os
import socket
import tempfile
from typing import TYPE_CHECKING

from ..core import ide_state
from ..core.cli import _run_cli, _resolve_project_path
from ..core.node_bridge import _run_node_script, invalidate_connection
from ..core.errors import ErrorCode
from ..models.schemas import WechatBuildInput
from ..utils.cdp_helpers import _format_cdp_logs_v2, _is_wxml_error
from ..utils.response import _ok, _fail
from .file_reader import _get_miniprogram_root

if TYPE_CHECKING:
    from .._compat import FastMCP


# 编译 stderr 行跳过模式（进度指示器 + 运行时噪音）
_COMPILE_SKIP_PREFIXES = (
    "- initialize", "✔", "- preparing", "- Fetching", "- Preview",
    "- compile", "- pack",
    # Node/Electron 运行时的弃用提示：IDE 2.02.2608060 Stable 的 cli 每次都打
    # `(node:PID) [DEP0040] DeprecationWarning: The punycode module is deprecated`
    # 与 `(Use \`Electron --trace-deprecation ...\`)`，与小程序代码无关，
    # 混进 warnings 会让 agent 误以为项目有告警（真机 2026-09-03 发现）。
    "(node:",
)

# 与 _COMPILE_SKIP_PREFIXES 配合：`(Use \`<可执行名> --trace-deprecation ...\`)` 这一行里的
# 可执行名跟平台走——macOS 是 Electron，Windows 是 微信开发者工具（真机 2026-09-04），
# 不能按前缀写死，按「(Use ` 开头且含 --trace-deprecation」判定。
_TRACE_DEPRECATION_HINT = "--trace-deprecation"

# 行分类关键词
_ERROR_KEYWORDS = ["error", "错误", "fail", "异常", "[error]"]
_WARNING_KEYWORDS = ["warning", "warn", "警告"]
_STATUS_KEYWORDS = ["✓", "√", "started", "success", "完成", "done"]

# 编译服务「致命启动错误」pattern：CLI returncode=0 时若 stderr 命中以下任一，
# 说明编译服务自身未起来（端口被占/权限问题），bundle 未刷新。必须降级为 fail。
# 背景：实测代理类软件占用 IDE 的 3799 端口时，compile 会返回 success:true 但 bundle 未刷新。
_FATAL_COMPILE_PATTERNS: tuple[str, ...] = (
    "EACCES",
    "EADDRINUSE",
    "#initialize-error",
    "permission denied",
    "listen EACCES",
    "listen failed",
)


def _detect_fatal_errors(errors: list[str]) -> list[str]:
    """从 errors 列表中筛出命中致命 pattern 的条目。"""
    return [e for e in errors if any(p in e for p in _FATAL_COMPILE_PATTERNS)]


def _check_npm_stale(proj: str) -> str | None:
    """检查 miniprogram_npm 是否缺失或早于 node_modules。

    compile 本身不会自动跑 build_npm。若用户在 node_modules 层安装/升级了依赖
    但忘了跑 build_npm，页面加载会报 `module ... is not defined`（#19）。

    Returns:
        warning 字符串，或 None（依赖状态正常/不涉及 npm）。
    """
    try:
        mp_root = _get_miniprogram_root(proj)
        node_modules = os.path.join(mp_root, "node_modules")
        miniprogram_npm = os.path.join(mp_root, "miniprogram_npm")

        if not os.path.isdir(node_modules):
            return None  # 项目未使用 npm，跳过

        if not os.path.isdir(miniprogram_npm):
            return (
                "检测到 miniprogram/node_modules 存在但 miniprogram_npm 缺失，"
                "请先执行 wechat_build(action='build_npm') 再 compile，"
                "否则页面加载可能报 `module ... is not defined`。"
            )

        nm_mtime = os.path.getmtime(node_modules)
        mpnpm_mtime = os.path.getmtime(miniprogram_npm)
        if mpnpm_mtime < nm_mtime:
            return (
                "node_modules 的 mtime 晚于 miniprogram_npm，依赖可能已更新未重新构建。"
                "建议执行 wechat_build(action='build_npm')。"
            )
    except Exception:
        pass  # 检测失败不应影响编译
    return None


def _classify_compile_line(line: str) -> str | None:
    """将 compile stderr 的单行分类为 error/warning/status，或 None（跳过行）。"""
    line = line.strip()
    if not line or line.startswith(_COMPILE_SKIP_PREFIXES):
        return None
    if line.startswith("(Use `") and _TRACE_DEPRECATION_HINT in line:
        return None
    lower = line.lower()
    if any(kw in lower for kw in _ERROR_KEYWORDS):
        return "error"
    if any(kw in lower for kw in _WARNING_KEYWORDS):
        return "warning"
    if any(kw in lower for kw in _STATUS_KEYWORDS):
        return "status"
    return "status"


def register_build(mcp: "FastMCP") -> None:
    """将 wechat_build 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_build",
        annotations={
            "title": "构建与发布",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_build)


async def wechat_build(params: WechatBuildInput) -> str:
    """构建、预览、上传小程序及 npm 管理。
    支持 action: compile(编译检查), preview(预览), upload(上传),
    build_npm(构建NPM), cache_clean(清缓存)。
    返回 JSON: {success, data, message, error_code?}。
    """
    try:
        if params.action == "compile":
            return await _action_compile(params)
        elif params.action == "preview":
            return await _action_preview(params)
        elif params.action == "upload":
            return await _action_upload(params)
        elif params.action == "build_npm":
            return await _action_build_npm(params)
        elif params.action == "cache_clean":
            return await _action_cache_clean(params)
        else:
            return _fail(ErrorCode.UNKNOWN_ERROR, f"未知 action: {params.action}")
    except ValueError as e:
        return _fail(ErrorCode.PROJECT_PATH_MISSING, str(e))
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")


def _port_open(port: int) -> bool:
    """TCP 层探测端口是否可连接。"""
    try:
        s = socket.create_connection(("localhost", port), timeout=0.5)
        s.close()
        return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _detect_ide_port(candidates: list[int] | None = None) -> int | None:
    """探测 IDE HTTP 端口。

    优先读 IDE 自己落盘的 `.ide` 文件（权威，随每次启动刷新）；读不到或该端口
    未监听时，才回退到硬编码候选列表逐个 TCP 探测。

    候选列表纯属经验值，实测 IDE 2.x 的端口（如 11071）根本不在其中，
    因此仅作兜底，不能作为主路径。
    """
    state_port = ide_state.read_ide_port()
    if state_port and _port_open(state_port):
        return state_port

    if candidates is None:
        candidates = [39797, 11321, 46498, 52673, 20847, 33621]
    for p in candidates:
        if _port_open(p):
            return p
    return None


async def _action_compile(params: WechatBuildInput) -> str:
    """触发编译并捕获错误和警告信息。编译成功后自动重连 automator。"""
    proj = _resolve_project_path(params.project_path)
    npm_warning = _check_npm_stale(proj)
    info_path = params.info_output or os.path.join(tempfile.gettempdir(), "wechat_compile_info.json")

    args = ["preview", "--project", proj, "--info-output", info_path]
    if params.port is not None:
        args.extend(["--port", str(params.port)])

    old_ide_port = _detect_ide_port()

    result = await _run_cli(*args, timeout=120)

    errors: list[str] = []
    warnings: list[str] = []
    status: list[str] = []
    compile_info: dict = {}

    stderr = result.get("stderr", "")
    if stderr:
        for line in stderr.split("\n"):
            category = _classify_compile_line(line)
            if category is None:
                continue
            elif category == "error":
                errors.append(line.strip())
            elif category == "warning":
                warnings.append(line.strip())
            else:
                status.append(line.strip())

    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                compile_info = json.load(f)
        except Exception:
            pass

    data = {
        "compiled": result["success"],
        "errors": errors,
        "warnings": warnings,
        "status": status,
        "compile_info": compile_info,
        "project": proj,
    }
    if npm_warning:
        data["npm_warning"] = npm_warning

    # ── CDP 采集 WXML 编译错误 ──
    wxml_errors: list[str] = []
    if result["success"]:
        try:
            cdp_result = await _run_node_script(
                "cdp_listener.js", "3", str(params.cdp_port), timeout=15,
            )
            cdp_logs = cdp_result.get("data", []) if isinstance(cdp_result, dict) else []
            if isinstance(cdp_logs, list) and cdp_logs:
                formatted = _format_cdp_logs_v2(cdp_logs, "concise", 50)
                wxml_errors = [
                    log["message"] for log in formatted["logs"]
                    if log["level"] == "error"
                    and _is_wxml_error(log["message"], log.get("source", ""))
                ]
        except Exception:
            pass  # CDP 采集失败不影响编译结果
    data["wxml_errors"] = wxml_errors

    if not result["success"]:
        data["automator_reconnected"] = False
        msg = f"编译失败，发现 {len(errors)} 个错误。"
        return _fail(ErrorCode.UNKNOWN_ERROR, msg, hint="; ".join(errors[:3]) if errors else "")

    # CLI returncode=0 但 stderr 含致命启动错误（端口被占/权限等），
    # 此时 bundle 实际未刷新，必须降级为失败，避免调用方拿到"假成功"后发布旧代码。
    fatal = _detect_fatal_errors(errors)
    if fatal:
        data["automator_reconnected"] = False
        data["fatal_errors"] = fatal
        return _fail(
            ErrorCode.UNKNOWN_ERROR,
            f"编译服务启动失败（检测到 {len(fatal)} 条致命错误），bundle 未刷新。",
            hint=f"常见原因：端口被占用或权限不足。首条错误：{fatal[0][:200]}",
            extra={"fatal_errors": fatal, "errors": errors},
        )

    # ── 编译成功后自动重连 automator ──
    # 注意: 使用默认端口 9420。若用户指定了非默认 auto_port，此处无法感知。
    auto_port = 9420
    port_was_active = False
    try:
        s = socket.create_connection(("localhost", auto_port), timeout=1)
        s.close()
        port_was_active = True
    except (ConnectionRefusedError, OSError, TimeoutError):
        pass

    if port_was_active:
        try:
            # 先清除 daemon 中可能缓存的旧连接
            await invalidate_connection(auto_port)
            # WS 级健康检查（automation.js 的 pageStack，ui_debug.js 无此 action）。
            # 此前固定 sleep(3) 再查一次；实测 compile 后 automator 多数情况下立即可用，
            # 改为立刻查、不通再每 0.5s 重试，上限约 4s，把等待时间还给快路径。
            ws_ready = False
            for attempt in range(8):
                health_result = await _run_node_script(
                    "automation.js",
                    "--port", str(auto_port),
                    "--action", "pageStack",
                    timeout=10,
                )
                ws_ready = bool(health_result.get("success", False))
                if ws_ready:
                    break
                await asyncio.sleep(0.5)
            data["automator_reconnected"] = True
            data["automator_verified"] = ws_ready
        except Exception as e:
            data["automator_reconnected"] = False
            data["reconnect_error"] = str(e)
    else:
        data["automator_reconnected"] = False

    # ── 编译后检测端口变化 ──
    new_ide_port = _detect_ide_port()
    if old_ide_port and new_ide_port and old_ide_port != new_ide_port:
        data["port_changed"] = True
        data["old_port"] = old_ide_port
        data["new_port"] = new_ide_port
    else:
        data["port_changed"] = False

    reconnect_status = ""
    if data.get("automator_reconnected") and data.get("automator_verified"):
        reconnect_status = " automator 已自动重连并验证就绪。"
    elif data.get("automator_reconnected"):
        reconnect_status = " automator 重连已触发，但端口未确认就绪。"
    elif port_was_active:
        reconnect_status = f" automator 重连失败：{data.get('reconnect_error', '未知错误')}。"

    wxml_note = f" 检测到 {len(wxml_errors)} 个 WXML 错误。" if wxml_errors else ""
    npm_note = " ⚠ npm 依赖状态异常，详见 npm_warning。" if npm_warning else ""
    msg = f"编译成功。{wxml_note}{reconnect_status}{npm_note}"
    return _ok(data, message=msg)


async def _action_preview(params: WechatBuildInput) -> str:
    """生成预览二维码。

    v0.9.5 改进：
      - qr_output/info_output 相对路径自动 resolve 为绝对路径（相对 project_path）
        （IDE CLI 不接受相对路径，见 #18）
      - 成功后对比 qr_output 调用前后 mtime，未刷新时发 warning
        （防止 compile 假成功 + preview 成功但二维码指向旧 bundle，见 #22）
    """
    proj = _resolve_project_path(params.project_path)
    args = ["preview", "--project", proj]
    if params.qr_format:
        args.extend(["--qr-format", params.qr_format])

    qr_path_abs: str | None = None
    if params.qr_output:
        qr_path_abs = params.qr_output if os.path.isabs(params.qr_output) \
            else os.path.abspath(os.path.join(proj, params.qr_output))
        parent = os.path.dirname(qr_path_abs)
        if parent:
            os.makedirs(parent, exist_ok=True)
        args.extend(["--qr-output", qr_path_abs])

    info_path_abs: str | None = None
    if params.info_output:
        info_path_abs = params.info_output if os.path.isabs(params.info_output) \
            else os.path.abspath(os.path.join(proj, params.info_output))
        parent = os.path.dirname(info_path_abs)
        if parent:
            os.makedirs(parent, exist_ok=True)
        args.extend(["--info-output", info_path_abs])

    if params.compile_condition:
        args.extend(["--compile-condition", params.compile_condition])
    if params.port is not None:
        args.extend(["--port", str(params.port)])
    if params.lang:
        args.extend(["--lang", params.lang])

    before_mtime = _safe_mtime(qr_path_abs) if qr_path_abs else 0.0

    result = await _run_cli(*args, timeout=120)
    if not result["success"]:
        return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "预览失败")

    data: dict = {"stdout": result["stdout"]}
    msg = "预览二维码已生成。"

    if qr_path_abs:
        data["qr_output"] = qr_path_abs
        after_mtime = _safe_mtime(qr_path_abs)
        data["qr_output_mtime"] = after_mtime
        if before_mtime > 0 and after_mtime <= before_mtime:
            data["qr_stale_warning"] = (
                "二维码文件未刷新（mtime 未变），bundle 可能仍是旧版本。"
                "检查最近一次 compile 是否有 fatal_errors，或重启 IDE 后重试。"
            )
            msg += " ⚠ 二维码文件可能未刷新，详见 qr_stale_warning。"
    if info_path_abs:
        data["info_output"] = info_path_abs

    return _ok(data, message=msg)


def _safe_mtime(path: str | None) -> float:
    """读取文件 mtime，不存在时返回 0.0。"""
    if not path:
        return 0.0
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


async def _action_upload(params: WechatBuildInput) -> str:
    """上传小程序代码到微信后台。"""
    if not params.version:
        return _fail(
            ErrorCode.PARAM_MISSING,
            "action='upload' 缺少必填参数: version",
            hint="请提供版本号，例如 version='1.0.0'",
        )
    proj = _resolve_project_path(params.project_path)
    args = ["upload", "--project", proj, "--version", params.version]
    if params.desc:
        args.extend(["--desc", params.desc])
    if params.info_output:
        args.extend(["--info-output", params.info_output])
    if params.port is not None:
        args.extend(["--port", str(params.port)])
    if params.lang:
        args.extend(["--lang", params.lang])

    result = await _run_cli(*args, timeout=120)
    if result["success"]:
        return _ok({"version": params.version, "stdout": result["stdout"]}, message=f"版本 {params.version} 上传成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "上传失败")


async def _action_build_npm(params: WechatBuildInput) -> str:
    """构建小程序 NPM 依赖。"""
    proj = _resolve_project_path(params.project_path)
    args = ["build-npm", "--project", proj]
    if params.compile_type:
        args.extend(["--compile-type", params.compile_type])
    if params.port is not None:
        args.extend(["--port", str(params.port)])

    result = await _run_cli(*args, timeout=120)
    if result["success"]:
        return _ok({}, message="NPM 构建成功。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "NPM 构建失败")


async def _action_cache_clean(params: WechatBuildInput) -> str:
    """清除指定类型的工具缓存。"""
    proj = _resolve_project_path(params.project_path)
    args = ["cache", "--clean", params.clean_type, "--project", proj]
    if params.port is not None:
        args.extend(["--port", str(params.port)])

    result = await _run_cli(*args)
    if result["success"]:
        return _ok({"clean_type": params.clean_type}, message=f"已清除 {params.clean_type} 缓存。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "清缓存失败")
