"""mcp SDK 双版本兼容导入。

mcp 2.0（2026-07-28）将 FastMCP 改名为 MCPServer 并移除了
mcp.server.fastmcp 模块；装饰器 API 不变，仅导入路径不同。
1.x 已进入维护模式（仅安全修复），仍需支持。
"""
try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp >= 2.0
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x（维护模式）

__all__ = ["FastMCP"]
