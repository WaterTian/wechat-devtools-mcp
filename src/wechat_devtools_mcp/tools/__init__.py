"""
tools 包：7 个聚合工具的统一注册入口。

注：云函数与云数据库管理请使用 CloudBase MCP —— 原 wechat_cloud 工具自 v0.9.5
起停用，源码已于开源时移除。
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._compat import FastMCP


def register_all_tools(mcp: "FastMCP") -> None:
    """将全部 7 个聚合工具注册到 FastMCP 实例。

    Args:
        mcp: FastMCP 实例。
    """
    from .ide import register_ide
    from .build import register_build
    from .automator import register_automator
    from .inspector import register_inspector
    from .screenshot import register_screenshot
    from .navigate import register_navigate
    from .file_reader import register_file

    register_ide(mcp)
    register_build(mcp)
    register_automator(mcp)
    register_inspector(mcp)
    register_screenshot(mcp)
    register_navigate(mcp)
    register_file(mcp)
