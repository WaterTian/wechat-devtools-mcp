"""automator start 连接验证逻辑测试（v0.9.5 起 verified = TCP && WS）。
v0.9.8 _action_start 改用 _run_cli 替代 subprocess.Popen。
"""
import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from wechat_devtools_mcp.tools.automator import (
    wechat_automator,
    _verify_port_ready,
    _verify_ws_ready,
)
from wechat_devtools_mcp.models.schemas import WechatAutomatorInput


def _mock_cli_success():
    """_run_cli 返回 CLI 成功的结果。"""
    return {"success": True, "stdout": "", "stderr": "", "return_code": 0}


def _mock_cli_failure():
    """_run_cli 返回 CLI 失败的结果。"""
    return {"success": False, "stdout": "", "stderr": "CLI failed", "return_code": 1}


@pytest.mark.asyncio
async def test_start_returns_ready_when_tcp_and_ws_ok():
    """CLI + TCP + WS 都通过时 verified=true，message 含 '已就绪'。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=True):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is True
        assert data["data"]["verified"] is True
        assert data["data"]["tcp_ready"] is True
        assert data["data"]["ws_ready"] is True
        assert data["data"]["verify_attempts"] == 1
        assert "已就绪" in data["message"]


@pytest.mark.asyncio
async def test_start_cli_fail_returns_error():
    """CLI auto 失败时立即返回 _fail，不等 TCP。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_failure()):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is False
        assert "CLI auto 执行失败" in data["message"]


@pytest.mark.asyncio
async def test_start_tcp_fail_returns_error():
    """CLI 成功但 TCP 未监听时返回 _fail。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()) as cli, \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=False), \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep", new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is False
        # 2026-09-03 起 cli auto 最多重试 3 轮再放弃
        assert cli.await_count == 3
        assert "未监听" in data["message"]


@pytest.mark.asyncio
async def test_start_ws_fail_triggers_invalidate_and_retry():
    """TCP OK 但 WS 第一次失败时应 invalidate + 2s + 再试，共 2 次。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
    ws_results = [False, True]

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, side_effect=ws_results) as mock_ws, \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True) as mock_inv, \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)

        assert data["data"]["verified"] is True
        assert data["data"]["verify_attempts"] == 2
        assert mock_ws.call_count == 2
        assert mock_inv.call_count == 1


@pytest.mark.asyncio
async def test_start_ws_fail_both_attempts_returns_retry_after_3s():
    """TCP OK 但 WS 两次都失败，返回 verified=false + retry_after_ms=3000。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=False), \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)

        assert data["data"]["verified"] is False
        assert data["data"]["tcp_ready"] is True
        assert data["data"]["ws_ready"] is False
        assert data["data"]["retry_after_ms"] == 3000
        assert data["data"]["verify_attempts"] == 2


@pytest.mark.asyncio
async def test_verify_ws_ready_calls_automation_js_pagestack():
    """_verify_ws_ready 必须调用 automation.js pageStack（驼峰），不是 ui_debug.js。"""
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, return_value={"success": True}) as mock_run:
        await _verify_ws_ready(9420)
        args = mock_run.call_args[0]
        assert args[0] == "automation.js"
        assert "pageStack" in args
        assert "page_stack" not in args


@pytest.mark.asyncio
async def test_verify_ws_ready_returns_false_on_exception():
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, side_effect=RuntimeError("daemon down")):
        assert await _verify_ws_ready(9420) is False


@pytest.mark.asyncio
async def test_verify_port_ready_max_attempts_5():
    """_verify_port_ready 默认 max_attempts=20，_action_start 传入 5。"""
    with patch("wechat_devtools_mcp.tools.automator.socket") as mock_socket:
        mock_socket.create_connection.side_effect = ConnectionRefusedError
        with patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
                   new_callable=AsyncMock) as mock_sleep:
            result = await _verify_port_ready(9420, max_attempts=5)
            assert result is False
            assert mock_sleep.call_count == 5
