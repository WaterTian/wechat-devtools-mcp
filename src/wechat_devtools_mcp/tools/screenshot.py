"""
wechat_screenshot 工具：截图（独立工具，无 action 参数）。

保持独立是因为 output_path 为特殊参数，与其他工具参数差异大。
output_path 可选，留空则自动保存到项目目录下 screenshots/ 文件夹。
"""
import os
import time
from typing import TYPE_CHECKING

from ..core.config import CLI_TIMEOUT, DEFAULT_PROJECT_PATH
from ..core.errors import ErrorCode
from ..core.node_bridge import _run_node_script
from ..models.schemas import WechatScreenshotInput
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP


def register_screenshot(mcp: "FastMCP") -> None:
    """将 wechat_screenshot 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_screenshot",
        annotations={
            "title": "捕获界面截图",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_screenshot)


def _resolve_output_path(output_path: str | None) -> str:
    """解析截图输出路径，未指定时自动生成到项目目录下 screenshots/ 文件夹。"""
    if output_path:
        return output_path
    base_dir = DEFAULT_PROJECT_PATH or os.getcwd()
    screenshots_dir = os.path.join(base_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")


async def wechat_screenshot(params: WechatScreenshotInput) -> str:
    """实时捕获当前小程序模拟器的界面截图。
    默认支持截取长图，自动滚动并拼接。
    output_path 可选，留空则自动保存到项目目录下 screenshots/ 文件夹。
    返回 JSON: {success, data: {path, width, height, segments}, message}。
    """
    try:
        resolved_path = _resolve_output_path(params.output_path)
        js_args = [
            "screenshot.js",
            "--port", str(params.auto_port),
            "--output", resolved_path,
            "--overlap", str(params.overlap),
        ]
        if not params.full_page:
            js_args.append("--no-full-page")
        if params.scroll_top is not None:
            js_args.extend(["--scroll-top", str(params.scroll_top)])
        if params.page_path:
            js_args.extend(["--page", params.page_path])

        result = await _run_node_script(*js_args, timeout=CLI_TIMEOUT + 60)

        if not result.get("success"):
            error_msg = result.get("error") or result.get("message") or "未知错误"
            return _fail(ErrorCode.UNKNOWN_ERROR, f"截图失败：{error_msg}")

        abs_path = result.get("path", resolved_path)
        file_size = 0
        try:
            file_size = os.path.getsize(abs_path)
        except OSError:
            pass

        return _ok(
            {
                "path": abs_path,
                "width": result.get("width", 0),
                "height": result.get("height", 0),
                "segments": result.get("segments", 1),
                "file_size": file_size,
            },
            message=f"截图成功，共 {result.get('segments', 1)} 段，已保存至 {abs_path}。",
        )
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"截图异常：{type(e).__name__}: {e}")
