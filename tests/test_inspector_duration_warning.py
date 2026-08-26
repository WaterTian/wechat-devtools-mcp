"""#21 inspector 短 duration 异常漏捕 warning。"""
import json
from unittest.mock import patch, AsyncMock
import pytest

from wechat_devtools_mcp.tools.inspector import wechat_inspector
from wechat_devtools_mcp.models.schemas import WechatInspectorInput


@pytest.mark.asyncio
async def test_short_duration_exception_emits_warning():
    fake = {
        "success": True,
        "console_logs": [], "exceptions": [],
        "summary": {"total_logs": 0, "errors": 0, "warnings": 0, "exceptions": 0},
    }
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=fake):
        params = WechatInspectorInput(action="console", duration=3, log_type="exception")
        result = json.loads(await wechat_inspector(params))
        assert result["success"] is True
        assert "duration_warning" in result["data"]


@pytest.mark.asyncio
async def test_long_duration_no_warning():
    fake = {
        "success": True,
        "console_logs": [], "exceptions": [],
        "summary": {"total_logs": 0, "errors": 0, "warnings": 0, "exceptions": 0},
    }
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=fake):
        params = WechatInspectorInput(action="console", duration=10, log_type="exception")
        result = json.loads(await wechat_inspector(params))
        assert "duration_warning" not in result["data"]


@pytest.mark.asyncio
async def test_console_only_short_duration_no_warning():
    """log_type='console' 不涉及异常，短 duration 不应告警。"""
    fake = {
        "success": True,
        "console_logs": [], "exceptions": [],
        "summary": {"total_logs": 0, "errors": 0, "warnings": 0, "exceptions": 0},
    }
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=fake):
        params = WechatInspectorInput(action="console", duration=3, log_type="console")
        result = json.loads(await wechat_inspector(params))
        assert "duration_warning" not in result["data"]
