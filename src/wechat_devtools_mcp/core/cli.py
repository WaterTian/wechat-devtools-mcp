"""
CLI 调用封装：执行微信开发者工具 CLI 命令。
"""
import asyncio
import os
import sys
import tempfile
from typing import Optional

from .config import CLI_PATH, CLI_TIMEOUT, DEFAULT_PROJECT_PATH


async def _run_cli(*args: str, timeout: int = CLI_TIMEOUT) -> dict:
    """执行微信开发者工具 CLI 命令并返回结果。

    使用临时文件捕获输出，避免与 MCP stdio 冲突。

    Args:
        *args: CLI 子命令及参数列表。
        timeout: 超时时间（秒）。

    Returns:
        dict: {success, stdout, stderr, return_code, command}。
    """
    cmd = [CLI_PATH] + list(args)

    if sys.platform == "win32" and CLI_PATH.lower().endswith(".bat"):
        cmd = ["cmd", "/c"] + cmd

    cmd_display = " ".join(cmd)

    stdout_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8')
    stderr_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8')

    try:
        stdout_file.close()
        stderr_file.close()

        if sys.platform == "win32":
            import subprocess
            cmd_str = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
            cmd_str = f'{cmd_str} > "{stdout_file.name}" 2> "{stderr_file.name}"'
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            with open(stdout_file.name, 'w') as out, open(stderr_file.name, 'w') as err:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=out,
                    stderr=err,
                )

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}秒）：{cmd_display}",
                "return_code": -1,
                "command": cmd_display,
            }

        with open(stdout_file.name, 'r', encoding='utf-8', errors='replace') as f:
            stdout_text = f.read().strip()
        with open(stderr_file.name, 'r', encoding='utf-8', errors='replace') as f:
            stderr_text = f.read().strip()

        return {
            "success": process.returncode == 0,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "return_code": process.returncode,
            "command": cmd_display,
        }

    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": (
                f"找不到 CLI 文件：{CLI_PATH}\n"
                "请确认微信开发者工具已安装，或设置 WECHAT_DEVTOOLS_CLI 环境变量。"
            ),
            "return_code": -1,
            "command": cmd_display,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"执行失败：{type(e).__name__}: {str(e)}",
            "return_code": -1,
            "command": cmd_display,
        }
    finally:
        try:
            os.unlink(stdout_file.name)
            os.unlink(stderr_file.name)
        except Exception:
            pass


def _build_global_args(
    project_path: Optional[str] = None,
    appid: Optional[str] = None,
    port: Optional[int] = None,
    lang: Optional[str] = None,
) -> list[str]:
    """构建 CLI 全局选项参数列表。"""
    args: list[str] = []
    if project_path:
        args.extend(["--project", project_path])
    if appid:
        args.extend(["--appid", appid])
    if port is not None:
        args.extend(["--port", str(port)])
    if lang:
        args.extend(["--lang", lang])
    return args


def _resolve_project_path(project_path: Optional[str]) -> str:
    """解析项目路径，未提供时使用默认路径。

    Args:
        project_path: 用户传入的路径，可为 None。

    Returns:
        有效的项目路径字符串。

    Raises:
        ValueError: 路径为空时抛出，含提示信息。
    """
    path = project_path or DEFAULT_PROJECT_PATH
    if not path:
        raise ValueError(
            "未提供有效的小程序项目路径！\n"
            "请通过以下任一方式设置：\n"
            "1. 配置环境变量 WECHAT_PROJECT_PATH\n"
            "2. 在工具参数中显式提供 project_path"
        )
    return path
