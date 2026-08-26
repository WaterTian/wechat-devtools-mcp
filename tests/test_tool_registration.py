"""工具注册完整性测试。"""
import pytest
from wechat_devtools_mcp._compat import FastMCP
from wechat_devtools_mcp.tools import register_all_tools


EXPECTED_TOOL_NAMES = [
    "wechat_ide", "wechat_build", "wechat_automator", "wechat_inspector",
    "wechat_screenshot", "wechat_navigate", "wechat_file",
]


class TestToolRegistration:
    """FastMCP 工具注册测试。"""

    def test_exactly_7_tools_registered(self, mcp_instance):
        """应恰好注册 7 个工具（wechat_cloud 自 v0.9.5 起已禁用）。"""
        tools = mcp_instance._tool_manager.list_tools()
        assert len(tools) == 7

    def test_all_expected_names_present(self, mcp_instance):
        tools = mcp_instance._tool_manager.list_tools()
        registered_names = {t.name for t in tools}
        for name in EXPECTED_TOOL_NAMES:
            assert name in registered_names, f"缺少工具: {name}"

    def test_cloud_tool_not_registered(self, mcp_instance):
        """wechat_cloud 应不被注册（已禁用）。"""
        tools = mcp_instance._tool_manager.list_tools()
        registered_names = {t.name for t in tools}
        assert "wechat_cloud" not in registered_names
