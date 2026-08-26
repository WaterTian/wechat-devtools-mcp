"""
Node.js daemon 通信封装：维护常驻 Node 进程，通过 NDJSON 协议通信。
"""
import asyncio
import atexit
import json
import os
import sys
from typing import Optional

from .config import _SCRIPTS_DIR, _NODE_PATH as _DEFAULT_NODE_PATH
from .errors import ErrorCode, _make_error

# daemon 单条 NDJSON 响应的最大字节数。
# asyncio 默认流上限是 64 KiB，而 IDE 2.x 下 6 秒 CDP 采集实测就有 634 KiB
# （IDE 外壳 target 贡献了六成日志量），超限时 readline 抛 LimitOverrunError，
# 结果被静默吞掉、采集恒返回 0 条。这里给足余量。
_STREAM_LIMIT: int = 16 * 1024 * 1024

# 模块级缓存
_node_available: Optional[bool] = None
_node_path_cache: Optional[str] = None
_NODE_PATH: str = _DEFAULT_NODE_PATH

# Daemon 进程状态
_daemon_process: Optional[asyncio.subprocess.Process] = None
_daemon_lock = asyncio.Lock()
_request_id: int = 0
_pending_responses: dict = {}  # id → asyncio.Future
_reader_task: Optional[asyncio.Task] = None


async def _check_node_available() -> tuple[bool, str]:
    """检测 Node.js 是否可用，结果缓存到模块级变量。"""
    global _node_available, _node_path_cache, _NODE_PATH

    if _node_available is not None:
        return _node_available, _node_path_cache or ""

    candidates = [_NODE_PATH]
    if sys.platform == "win32":
        candidates += [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            os.path.expandvars(r"%APPDATA%\nvm\current\node.exe"),
            os.path.expandvars(r"%ProgramFiles%\nodejs\node.exe"),
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/opt/homebrew/bin/node",
            "/usr/local/bin/node",
            os.path.expanduser("~/.nvm/versions/node/lts/bin/node"),
        ]
    elif sys.platform.startswith("linux"):
        candidates += [
            "/usr/bin/node",
            "/usr/local/bin/node",
            os.path.expanduser("~/.nvm/versions/node/lts/bin/node"),
        ]

    for candidate in candidates:
        try:
            process = await asyncio.create_subprocess_exec(
                candidate, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            if process.returncode == 0:
                version = stdout.decode("utf-8", errors="replace").strip()
                node_path = candidate if os.path.isabs(candidate) else f"node ({version})"
                _node_available = True
                _node_path_cache = node_path
                if os.path.isabs(candidate) and os.path.exists(candidate):
                    _NODE_PATH = candidate
                return True, node_path
        except Exception:
            continue

    _node_available = False
    _node_path_cache = ""
    return False, ""


async def _ensure_daemon() -> None:
    """确保 daemon 进程正在运行。"""
    global _daemon_process, _reader_task, _pending_responses

    async with _daemon_lock:
        if _daemon_process is not None and _daemon_process.returncode is None:
            return

        _pending_responses.clear()
        if _reader_task and not _reader_task.done():
            _reader_task.cancel()

        bundle_path = os.path.join(_SCRIPTS_DIR, "dist", "daemon.bundle.js")
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"找不到 daemon bundle: {bundle_path}")

        _daemon_process = await asyncio.create_subprocess_exec(
            _NODE_PATH, bundle_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_SCRIPTS_DIR,
            limit=_STREAM_LIMIT,
        )

        try:
            ready_line = await asyncio.wait_for(
                _daemon_process.stdout.readline(), timeout=10
            )
            ready_msg = json.loads(ready_line.decode("utf-8", errors="replace").strip())
            if not ready_msg.get("ready"):
                raise RuntimeError("daemon 未发送 ready 信号")
        except asyncio.TimeoutError:
            _kill_daemon()
            raise RuntimeError("daemon 启动超时（10秒）")

        _reader_task = asyncio.create_task(_response_reader())


async def _response_reader() -> None:
    """后台任务：持续读取 daemon stdout 并分发到对应的 Future。"""
    global _daemon_process
    try:
        while _daemon_process and _daemon_process.returncode is None:
            line = await _daemon_process.stdout.readline()
            if not line:
                break

            try:
                msg = json.loads(line.decode("utf-8", errors="replace").strip())
            except json.JSONDecodeError:
                continue

            msg_id = msg.get("id")
            if msg_id is not None and msg_id in _pending_responses:
                future = _pending_responses.pop(msg_id)
                if not future.done():
                    if msg.get("success") is False:
                        # 优先用顶层 error，fallback 到 data.error (daemon respond 把 error 嵌套在 data 内)
                        err = msg.get("error") or (msg.get("data", {}) or {}).get("error") or "未知错误"
                        future.set_result({
                            "success": False,
                            "error": err,
                        })
                    else:
                        result = msg.get("data", {})
                        if isinstance(result, list):
                            result = {"success": True, "data": result}
                        elif isinstance(result, dict) and "success" not in result:
                            result["success"] = True
                        future.set_result(result)
    except asyncio.CancelledError:
        pass
    except (ValueError, asyncio.LimitOverrunError) as e:
        # 单条响应超过 _STREAM_LIMIT。留下可诊断的信息，不要静默吞掉。
        sys.stderr.write(
            f"[node_bridge] 响应超过流上限 {_STREAM_LIMIT} 字节，读取中止: {e}\n"
        )
    except Exception as e:
        sys.stderr.write(f"[node_bridge] reader error: {e}\n")
    finally:
        for future in _pending_responses.values():
            if not future.done():
                future.set_exception(ConnectionError("daemon 进程已退出"))
        _pending_responses.clear()


async def _send_request(request_id: int, script: str, args: list) -> None:
    """向 daemon stdin 写入一条 NDJSON 请求。"""
    global _daemon_process
    if _daemon_process is None or _daemon_process.stdin is None:
        raise ConnectionError("daemon 未启动")

    msg = json.dumps({"id": request_id, "script": script, "args": args})
    _daemon_process.stdin.write((msg + "\n").encode("utf-8"))
    await _daemon_process.stdin.drain()


async def _read_response(request_id: int, timeout: int) -> dict:
    """等待指定 id 的响应。"""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    _pending_responses[request_id] = future

    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        _pending_responses.pop(request_id, None)
        return {
            "success": False,
            "error": f"daemon 响应超时（{timeout}秒）",
        }


def _kill_daemon() -> None:
    """强制终止 daemon 进程。"""
    global _daemon_process, _reader_task
    if _daemon_process and _daemon_process.returncode is None:
        try:
            _daemon_process.kill()
        except Exception:
            pass
    _daemon_process = None
    if _reader_task and not _reader_task.done():
        _reader_task.cancel()
    _reader_task = None
    _pending_responses.clear()


def _atexit_cleanup() -> None:
    """进程退出时清理 daemon。"""
    _kill_daemon()


atexit.register(_atexit_cleanup)


async def _run_node_script(
    script_name: str,
    *extra_args: str,
    timeout: int = 120,
) -> dict:
    """调用 daemon 中的 handler，返回解析后的 JSON 结果。

    签名与 v0.8.0 完全一致，所有 tool handler 无需修改。
    """
    global _request_id

    node_ok, node_path = await _check_node_available()
    if not node_ok:
        return json.loads(_make_error(
            ErrorCode.NODE_NOT_FOUND,
            "未检测到 Node.js，无法执行自动化脚本。",
            hint="请安装 Node.js（>= 8.0）并配置 PATH 环境变量。",
        ))

    script = os.path.splitext(script_name)[0]
    args_list = list(extra_args)

    for attempt in range(2):
        try:
            await _ensure_daemon()

            _request_id += 1
            req_id = _request_id

            await _send_request(req_id, script, args_list)
            result = await _read_response(req_id, timeout)
            if isinstance(result, list):
                result = {"success": True, "data": result}
            return result

        except (ConnectionError, FileNotFoundError, RuntimeError) as e:
            if attempt == 0:
                _kill_daemon()
                continue
            return {
                "success": False,
                "error": f"daemon 通信失败: {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"执行失败: {type(e).__name__}: {e}",
            }

    return {"success": False, "error": "daemon 启动失败（重试耗尽）"}


async def invalidate_connection(port: int) -> bool:
    """通知 daemon 清除指定端口的缓存连接。

    用于 compile 后强制断开旧的 automator 连接，
    确保下次请求时建立新连接。
    """
    result = await _run_node_script("invalidate", str(port), timeout=10)
    return result.get("invalidated", False)
