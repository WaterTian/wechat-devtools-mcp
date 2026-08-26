"""node_bridge daemon 生命周期和协议测试。"""
import json
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from wechat_devtools_mcp.core.node_bridge import _run_node_script


@pytest.mark.asyncio
async def test_run_node_script_returns_success():
    """_run_node_script 正常调用时返回 handler 的 data。"""
    mock_result = {"success": True, "action": "tap", "selector": ".btn"}

    with patch("wechat_devtools_mcp.core.node_bridge._ensure_daemon") as mock_ensure, \
         patch("wechat_devtools_mcp.core.node_bridge._send_request"), \
         patch("wechat_devtools_mcp.core.node_bridge._read_response", new_callable=AsyncMock, return_value=mock_result):
        mock_ensure.return_value = None
        result = await _run_node_script("automation.js", "--port", "9420", "--action", "tap", "--selector", ".btn")
        assert result["success"] is True
        assert result["action"] == "tap"


@pytest.mark.asyncio
async def test_run_node_script_returns_error():
    """handler 返回错误时 _run_node_script 也返回错误。"""
    mock_result = {"success": False, "error": "Connection closed"}

    with patch("wechat_devtools_mcp.core.node_bridge._ensure_daemon"), \
         patch("wechat_devtools_mcp.core.node_bridge._send_request"), \
         patch("wechat_devtools_mcp.core.node_bridge._read_response", new_callable=AsyncMock, return_value=mock_result):
        result = await _run_node_script("automation.js", "--action", "tap")
        assert result["success"] is False
        assert "Connection closed" in result["error"]


@pytest.mark.asyncio
async def test_run_node_script_timeout():
    """响应超时时返回超时错误。"""
    timeout_result = {"success": False, "error": "daemon 响应超时（1秒）"}

    with patch("wechat_devtools_mcp.core.node_bridge._ensure_daemon"), \
         patch("wechat_devtools_mcp.core.node_bridge._send_request"), \
         patch("wechat_devtools_mcp.core.node_bridge._read_response", new_callable=AsyncMock, return_value=timeout_result):
        result = await _run_node_script("automation.js", "--action", "tap", timeout=1)
        assert result["success"] is False
        assert "超时" in result["error"]


@pytest.mark.asyncio
async def test_run_node_script_node_not_found():
    """Node.js 不可用时返回错误。"""
    with patch("wechat_devtools_mcp.core.node_bridge._check_node_available", new_callable=AsyncMock, return_value=(False, "")):
        result = await _run_node_script("automation.js")
        assert result["success"] is False
        assert "Node.js" in str(result.get("message", result.get("error", "")))


@pytest.mark.asyncio
async def test_run_node_script_daemon_restart_on_death():
    """daemon 意外退出时自动重启并重发请求。"""
    call_count = 0
    mock_result = {"success": True, "action": "tap"}

    async def mock_ensure():
        nonlocal call_count
        call_count += 1

    async def mock_read(*a, **kw):
        if call_count <= 1:
            raise ConnectionError("daemon died")
        return mock_result

    with patch("wechat_devtools_mcp.core.node_bridge._ensure_daemon", new_callable=AsyncMock, side_effect=mock_ensure), \
         patch("wechat_devtools_mcp.core.node_bridge._send_request"), \
         patch("wechat_devtools_mcp.core.node_bridge._read_response", new_callable=AsyncMock, side_effect=mock_read), \
         patch("wechat_devtools_mcp.core.node_bridge._kill_daemon"):
        result = await _run_node_script("automation.js", "--action", "tap")
        assert result["success"] is True
        assert call_count == 2


@pytest.mark.asyncio
async def test_run_node_script_list_response_wrapped():
    """daemon 返回 list 类型 data 时，应包装为 dict。"""
    mock_result = [{"type": "LOG_ENTRY", "text": "error"}]

    with patch("wechat_devtools_mcp.core.node_bridge._ensure_daemon"), \
         patch("wechat_devtools_mcp.core.node_bridge._send_request"), \
         patch("wechat_devtools_mcp.core.node_bridge._read_response", new_callable=AsyncMock, return_value=mock_result):
        result = await _run_node_script("cdp_listener.js", "5", "9222")
        assert isinstance(result, dict)
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
