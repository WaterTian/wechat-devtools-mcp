"""
wechat_ide 工具：IDE 生命周期管理。

合并原 wechat_open、wechat_login、wechat_is_login、
wechat_close_project、wechat_quit_ide、wechat_get_status。
"""
import asyncio
import json
import os
import sys
from typing import TYPE_CHECKING

from ..core import ide_state
from ..core.cli import _run_cli, _build_global_args, _resolve_project_path
from ..core.config import CLI_PATH, DEFAULT_PROJECT_PATH
from .. import __version__
from ..core.errors import ErrorCode
from ..core.node_bridge import _check_node_available, _run_node_script
from ..models.schemas import WechatIdeInput
from ..utils.cdp_helpers import _format_cdp_logs_v2
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP


def register_ide(mcp: "FastMCP") -> None:
    """将 wechat_ide 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_ide",
        annotations={
            "title": "IDE 生命周期管理",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_ide)


async def wechat_ide(params: WechatIdeInput) -> str:
    """微信开发者工具 IDE 生命周期管理。
    支持 action: open(打开IDE/项目), login(扫码登录), is_login(检查登录),
    close(关闭项目), quit(退出IDE), status(环境诊断)。
    返回 JSON: {success, data, message, error_code?}。
    """
    try:
        if params.action == "open":
            return await _action_open(params)
        elif params.action == "login":
            return await _action_login(params)
        elif params.action == "is_login":
            return await _action_is_login(params)
        elif params.action == "close":
            return await _action_close(params)
        elif params.action == "quit":
            return await _action_quit(params)
        elif params.action == "status":
            return await _action_status()
        else:
            return _fail(ErrorCode.UNKNOWN_ERROR, f"未知 action: {params.action}")
    except ValueError as e:
        return _fail(ErrorCode.PROJECT_PATH_MISSING, str(e))
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")


def _read_bundle_executable(contents: str) -> str:
    """读取 macOS .app 的 Info.plist 中的 CFBundleExecutable。

    IDE 1.x(NW.js) 是 wechatdevtools，2.x(Electron) 是 Electron，
    读 plist 比硬编码文件名更能跟上官方大版本变动。读取失败返回空串由调用方兜底。
    """
    try:
        import plistlib
        with open(os.path.join(contents, "Info.plist"), "rb") as f:
            return plistlib.load(f).get("CFBundleExecutable") or ""
    except Exception:
        return ""


def _resolve_ide_executable_for_cdp() -> tuple[list[str], str, str]:
    """从 CLI_PATH 推导 IDE 主程序启动命令前缀、kill 模式与运行时类型。

    Returns:
        (cmd_prefix, kill_pattern, runtime):
          cmd_prefix  - 启动 IDE 主程序的命令前缀（不含 --remote-debugging-port）
          kill_pattern - taskkill 镜像名（Windows）或 pkill -f 模式（macOS，用 .app 包路径）
          runtime     - "nwjs" / "electron" / "win32"，决定项目如何打开

    macOS 双轨（2026-08-20 实测 IDE 2.02.2607271）：
      - 1.x 是 NW.js，主程序 wechatdevtools + Resources/package.nw 入口
      - 2.x 是 Electron，入口是 Contents/MacOS/Electron，package.nw 已不存在，
        且不再识别 --project，需由调用方在进程起来后用 CLI 打开项目

    Raises:
        FileNotFoundError: IDE 主程序缺失。
        NotImplementedError: 当前平台不支持 cdp_enabled。
    """
    if sys.platform == "win32":
        exe = CLI_PATH.replace("cli.bat", "微信开发者工具.exe")
        return [exe], "wechatdevtools.exe", "win32"

    if sys.platform == "darwin":
        # CLI_PATH 形如 /Applications/wechatwebdevtools.app/Contents/MacOS/cli
        # 显式使用 forward slash，避免 os.path.join 在跨平台调试时引入反斜杠
        cli_dir = CLI_PATH.rsplit("/", 1)[0]
        contents = cli_dir.rsplit("/", 1)[0]
        # kill 模式用 .app 包路径：1.x 的 wechatdevtools 与 2.x 的 Electron
        # 命令行都以它开头，一个模式覆盖两代。
        # （旧模式 "wechatdevtools" 匹配不到 2.x，因为 "wechatwebdevtools" 里没有该子串。）
        kill_pattern = contents.rsplit("/", 1)[0]

        package_nw = f"{contents}/Resources/package.nw"
        if os.path.exists(package_nw):
            ide_exe = f"{cli_dir}/{_read_bundle_executable(contents) or 'wechatdevtools'}"
            if not os.path.exists(ide_exe):
                raise FileNotFoundError(f"找不到 macOS IDE 主程序：{ide_exe}")
            return [ide_exe, package_nw], kill_pattern, "nwjs"

        ide_exe = f"{cli_dir}/{_read_bundle_executable(contents) or 'Electron'}"
        if not os.path.exists(ide_exe):
            raise FileNotFoundError(f"找不到 macOS IDE 主程序：{ide_exe}")
        return [ide_exe], kill_pattern, "electron"

    raise NotImplementedError(f"cdp_enabled 暂不支持平台：{sys.platform}")


def _port_listening(port: int) -> bool:
    """TCP 层探测端口是否已在监听。"""
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
        s.close()
        return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


async def _wait_ide_ready(cdp_port: int, timeout: int = 60) -> tuple[bool, bool]:
    """等待刚启动的 IDE 就绪，返回 (cdp_ready, service_ready)。

    为什么必须等：IDE 有单实例锁。若在自己起的实例尚未就绪时就调 `cli open`，
    CLI 会另起一个**不带 CDP 的**实例，我们那个反被挤掉——现象是项目正常打开
    但 CDP 端口连不上（实测踩过）。

    就绪判据两条：
      1. CDP 端口开始监听 —— 说明 Electron 的 DevTools server 起来了
      2. `.ide` 记录的 IDE 服务端口开始监听 —— 说明 CLI 能连上这个实例
    """
    deadline = asyncio.get_running_loop().time() + timeout
    cdp_ready = False
    service_ready = False
    while asyncio.get_running_loop().time() < deadline:
        if not cdp_ready:
            cdp_ready = _port_listening(cdp_port)
        if not service_ready:
            svc = ide_state.read_ide_port()
            service_ready = bool(svc and _port_listening(svc))
        if cdp_ready and service_ready:
            return True, True
        await asyncio.sleep(1)
    return cdp_ready, service_ready


async def _kill_existing_ide(kill_pattern: str) -> None:
    """跨平台 kill 已运行的 IDE 主程序，并等待 2s 确保端口释放。"""
    import subprocess
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", kill_pattern],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    elif sys.platform == "darwin":
        subprocess.run(
            ["pkill", "-9", "-f", kill_pattern],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    await asyncio.sleep(2)


async def _action_open(params: WechatIdeInput) -> str:
    """打开微信开发者工具 IDE 或项目。"""
    import subprocess

    runtime = ""
    if params.cdp_enabled:
        try:
            cmd_prefix, kill_pattern, runtime = _resolve_ide_executable_for_cdp()
        except (FileNotFoundError, NotImplementedError) as e:
            return _fail(ErrorCode.CLI_NOT_FOUND, str(e))

        cmd_args = list(cmd_prefix) + [f"--remote-debugging-port={params.cdp_port}"]
        # IDE 2.x(Electron) 不再识别 --project（实测 projectpath 为空），
        # 改为进程带 CDP 起来后再用 CLI open 打开项目，见下方两步式处理。
        if params.project_path and runtime != "electron":
            if sys.platform == "darwin":
                cmd_args.append(f"--project={params.project_path}")
            else:
                cmd_args.extend(["--project", params.project_path])

        await _kill_existing_ide(kill_pattern)
    else:
        cli_args = ["open"]
        cli_args.extend(_build_global_args(
            project_path=params.project_path,
            appid=params.appid,
            port=params.port,
            lang=params.lang,
        ))
        if sys.platform == "win32" and CLI_PATH.lower().endswith(".bat"):
            cmd_args = ["cmd", "/c", CLI_PATH] + cli_args
        else:
            cmd_args = [CLI_PATH] + cli_args

    try:
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            cmd_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )

        if params.cdp_enabled:
            # 这里起的是 GUI 主程序，正常情况下永不退出，等它没有意义。
            # 且 asyncio.to_thread(proc.wait) 的线程不可取消，超时后会一直挂着，
            # 拖住解释器退出。改为短暂轮询，只用于捕捉「起不来就立刻挂掉」。
            for _ in range(6):
                await asyncio.sleep(0.5)
                if proc.poll() is not None:
                    break
            if proc.returncode not in (None, 0):
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    f"IDE 主程序启动后立即退出（返回码 {proc.returncode}）。",
                    hint="确认 IDE 未被其它实例占用，或 CDP 端口未被占用。",
                    extra={"cdp_port": params.cdp_port, "runtime": runtime},
                )
        else:
            # CLI 路径的 cli open 会正常退出，等它拿到结果
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=15)
            except asyncio.TimeoutError:
                pass

        cdp_note = f"CDP 调试端口已开启（{params.cdp_port}）" if params.cdp_enabled else ""

        # IDE 2.x(Electron) 两步式：进程已带 CDP 起来，再让 CLI 打开项目。
        # 必须等到 CDP 与 IDE 服务都监听后才能调 CLI，否则 CLI 会另起一个
        # 不带 CDP 的实例，我们这个反被单实例锁挤掉。
        project_opened = None
        cdp_ready = None
        if params.cdp_enabled and runtime == "electron":
            cdp_ready, service_ready = await _wait_ide_ready(params.cdp_port, timeout=60)
            if not cdp_ready:
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    f"IDE 已启动但 CDP 端口 {params.cdp_port} 未监听。",
                    hint=(
                        f"该端口可能被占用（可用 curl 127.0.0.1:{params.cdp_port}/json/version "
                        "确认端口上是谁），换一个 cdp_port 重试。"
                    ),
                    extra={"cdp_port": params.cdp_port, "runtime": runtime},
                )
            if not service_ready:
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    "IDE 服务端口在 60 秒内未就绪，无法继续打开项目。",
                    hint="确认开发者工具的服务端口已开启（设置 → 安全设置 → 服务端口）。",
                    extra={"cdp_port": params.cdp_port, "runtime": runtime},
                )

        if params.cdp_enabled and runtime == "electron" and params.project_path:
            open_result = await _run_cli(
                "open", "--project", params.project_path, timeout=90,
            )
            project_opened = open_result["success"]
            if not project_opened:
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    "IDE 已带 CDP 启动，但打开项目失败。",
                    hint=(open_result.get("stderr") or "")[:200]
                    or "IDE 可能仍在初始化，稍后重试 wechat_ide(action='open')。",
                    extra={"cdp_port": params.cdp_port, "runtime": runtime},
                )

        # CDP 启动健康检查：采集 5 秒日志，检测启动阶段致命错误
        if params.cdp_enabled:
            await asyncio.sleep(5)  # 等待小程序页面加载
            cdp_result = await _run_node_script(
                "cdp_listener.js", "5", str(params.cdp_port), timeout=20,
            )
            raw_logs = cdp_result.get("data", cdp_result.get("logs", []))
            if not isinstance(raw_logs, list):
                raw_logs = []
            formatted = _format_cdp_logs_v2(raw_logs, "concise", 50, filter_startup_noise=True)
            error_count = formatted["summary"]["errors"]
            if error_count > 0:
                error_logs = [
                    log for log in formatted["logs"] if log["level"] == "error"
                ]
                return _fail(
                    ErrorCode.UNKNOWN_ERROR,
                    f"小程序启动阶段检测到 {error_count} 个错误，页面可能无法正常显示。",
                    hint="请先修复以下启动错误，再继续后续操作。",
                    extra={"startup_errors": error_logs, "cdp_summary": formatted["summary"]},
                )

        data: dict = {
            "cdp_enabled": params.cdp_enabled,
            "cdp_port": params.cdp_port if params.cdp_enabled else None,
        }
        if runtime:
            data["ide_runtime"] = runtime
        if project_opened is not None:
            data["project_opened"] = project_opened
        if cdp_ready is not None:
            data["cdp_ready"] = cdp_ready
        return _ok(data, message=f"IDE 已在后台启动。{cdp_note}")
    except FileNotFoundError:
        return _fail(
            ErrorCode.CLI_NOT_FOUND,
            f"找不到微信开发者工具文件：{cmd_args[0]}",
            hint="请确认微信开发者工具已安装，或通过 WECHAT_DEVTOOLS_CLI 指定路径。",
        )
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"启动失败：{type(e).__name__}: {e}")


async def _action_login(params: WechatIdeInput) -> str:
    """登录微信开发者工具，生成二维码供扫码。"""
    args = ["login"]
    if params.qr_format:
        args.extend(["--qr-format", params.qr_format])
    if params.qr_output:
        args.extend(["--qr-output", params.qr_output])
    if params.result_output:
        args.extend(["--result-output", params.result_output])
    if params.port is not None:
        args.extend(["--port", str(params.port)])
    if params.lang:
        args.extend(["--lang", params.lang])

    result = await _run_cli(*args, timeout=120)
    if result["success"]:
        return _ok({"stdout": result["stdout"]}, message="登录二维码已生成。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or result.get("stdout") or "登录失败")


async def _action_is_login(params: WechatIdeInput) -> str:
    """检查微信开发者工具当前是否已登录。"""
    args = ["islogin"]
    args.extend(_build_global_args(project_path=params.project_path, appid=params.appid, port=params.port))
    result = await _run_cli(*args)
    logged_in = result["success"]
    return _ok(
        {"logged_in": logged_in, "stdout": result.get("stdout", "")},
        message="已登录" if logged_in else "未登录",
    )


async def _action_close(params: WechatIdeInput) -> str:
    """关闭指定小程序项目窗口。"""
    proj = _resolve_project_path(params.project_path)
    args = ["close", "--project", proj]
    if params.port is not None:
        args.extend(["--port", str(params.port)])
    result = await _run_cli(*args)
    if result["success"]:
        return _ok({}, message="项目窗口已关闭。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "关闭失败")


async def _action_quit(params: WechatIdeInput) -> str:
    """退出整个微信开发者工具 IDE。"""
    args = ["quit"]
    if params.port is not None:
        args.extend(["--port", str(params.port)])
    result = await _run_cli(*args)
    if result["success"]:
        return _ok({}, message="IDE 已退出。")
    return _fail(ErrorCode.UNKNOWN_ERROR, result.get("stderr") or "退出失败")


async def _action_status() -> str:
    """返回 MCP 服务运行状态和环境配置信息。"""
    project_path = DEFAULT_PROJECT_PATH or ""
    cli_path = CLI_PATH

    project_exists = os.path.isdir(project_path) if project_path else False
    cli_exists = os.path.exists(cli_path)
    node_ok, node_path = await _check_node_available()

    service_port_on = ide_state.read_service_port_enabled()
    ide_port = ide_state.read_ide_port()

    data: dict = {
        "mcp_version": __version__,
        "cli_path": cli_path,
        "cli_exists": cli_exists,
        "project_path": project_path or "未配置",
        "project_exists": project_exists,
        "node_available": node_ok,
        "node_path": node_path,
        # 由 IDE 自己落盘的运行时状态读出，读不到为 None（表示无法判断）
        "service_port_enabled": service_port_on,
        "ide_port": ide_port,
    }

    if project_exists:
        config_path = os.path.join(project_path, "project.config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                data["project_name"] = config.get("projectname", "未知")
                data["appid"] = config.get("appid", "未知")
                data["lib_version"] = config.get("libVersion", "未知")
            except Exception:
                pass

    hints = []
    if not cli_exists:
        hints.append(f"CLI 文件不存在：{cli_path}，请设置 WECHAT_DEVTOOLS_CLI 环境变量")
    if not project_exists:
        hints.append("项目路径未配置或不存在，请设置 WECHAT_PROJECT_PATH 环境变量")
    if not node_ok:
        hints.append("Node.js 未检测到，请安装并配置 PATH")
    if service_port_on is False:
        hints.append(
            "开发者工具的服务端口未开启（设置 → 安全设置 → 服务端口），"
            "这是 CLI_TIMEOUT 的头号原因，所有 CLI 操作都会超时"
        )

    return _ok(data, message="状态正常" if not hints else "；".join(hints))
