"""daemon invalidate 命令测试。"""
import pytest
from unittest.mock import patch, AsyncMock

from wechat_devtools_mcp.core.node_bridge import invalidate_connection


@pytest.mark.asyncio
async def test_invalidate_sends_correct_request():
    """invalidate_connection 应发送 script='invalidate' 请求。"""
    fake_result = {"success": True, "invalidated": True, "port": 9420}
    with patch("wechat_devtools_mcp.core.node_bridge._run_node_script",
               new_callable=AsyncMock, return_value=fake_result) as mock_run:
        result = await invalidate_connection(9420)
        mock_run.assert_called_once_with("invalidate", "9420", timeout=10)
        assert result is True


@pytest.mark.asyncio
async def test_invalidate_returns_false_on_no_connection():
    """无缓存连接时 invalidate 返回 False。"""
    fake_result = {"success": True, "invalidated": False, "port": 9420}
    with patch("wechat_devtools_mcp.core.node_bridge._run_node_script",
               new_callable=AsyncMock, return_value=fake_result):
        result = await invalidate_connection(9420)
        assert result is False


@pytest.mark.asyncio
async def test_invalidate_returns_false_on_error():
    """daemon 通信失败时 invalidate 返回 False。"""
    fake_result = {"success": False, "error": "daemon 响应超时"}
    with patch("wechat_devtools_mcp.core.node_bridge._run_node_script",
               new_callable=AsyncMock, return_value=fake_result):
        result = await invalidate_connection(9420)
        assert result is False
