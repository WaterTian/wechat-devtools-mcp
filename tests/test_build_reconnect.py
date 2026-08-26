"""compile 后自动重连 automator 的测试。"""
import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from wechat_devtools_mcp.tools.build import wechat_build
from wechat_devtools_mcp.models.schemas import WechatBuildInput


@pytest.mark.asyncio
async def test_compile_reconnects_automator(set_env_vars):
    """compile 成功后应通过 WebSocket 健康检查自动重连 automator。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    fake_health = {"success": True, "data": {"pages": []}}
    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
         patch("wechat_devtools_mcp.tools.build.invalidate_connection", new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=fake_health) as mock_health, \
         patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
        mock_socket.create_connection.return_value = MagicMock()

        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        assert result["success"] is True
        assert result["data"]["automator_reconnected"] is True
        assert result["data"]["automator_verified"] is True
        # _run_node_script 被调用两次：CDP 采集 + 健康检查
        health_calls = [c for c in mock_health.call_args_list if 'automation.js' in c.args]
        assert len(health_calls) == 1
        # 且 action 必须是驼峰 pageStack（v0.9.5 修复 ui_debug.js page_stack bug）
        assert any('pageStack' in str(c) for c in health_calls)


@pytest.mark.asyncio
async def test_compile_skip_reconnect_when_port_closed(set_env_vars):
    """automator 端口不可达时不尝试重连。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket:
        mock_socket.create_connection.side_effect = ConnectionRefusedError
        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        assert result["success"] is True
        assert result["data"].get("automator_reconnected") is False


@pytest.mark.asyncio
async def test_compile_reconnect_failure_does_not_block(set_env_vars):
    """重连失败不应阻塞 compile 成功返回。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
         patch("wechat_devtools_mcp.tools.build.invalidate_connection", new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, side_effect=Exception("reconnect failed")), \
         patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
        mock_socket.create_connection.return_value = MagicMock()

        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        assert result["success"] is True
        assert result["data"]["automator_reconnected"] is False
        assert "reconnect_error" in result["data"]


@pytest.mark.asyncio
async def test_compile_detects_port_change(set_env_vars):
    """compile 后检测 IDE HTTP 端口变化。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    fake_health = {"success": True, "data": {"pages": []}}
    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
         patch("wechat_devtools_mcp.tools.build.invalidate_connection", new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=fake_health), \
         patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock), \
         patch("wechat_devtools_mcp.tools.build._detect_ide_port") as mock_detect:
        mock_socket.create_connection.return_value = MagicMock()
        # 模拟端口从 39797 变为 11321
        mock_detect.side_effect = [39797, 11321]

        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        assert result["data"]["port_changed"] is True
        assert result["data"]["old_port"] == 39797
        assert result["data"]["new_port"] == 11321


@pytest.mark.asyncio
async def test_compile_invalidates_before_health_check(set_env_vars):
    """compile 成功后应先 invalidate 旧连接，再做 WebSocket 健康检查。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    call_order = []

    async def track_invalidate(port):
        call_order.append(("invalidate", port))
        return True

    async def track_health(*args, **kwargs):
        call_order.append(("health_check",))
        return {"success": True, "data": {"pages": []}}

    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
         patch("wechat_devtools_mcp.tools.build.invalidate_connection", side_effect=track_invalidate), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", side_effect=track_health), \
         patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
        mock_socket.create_connection.return_value = MagicMock()
        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        assert result["success"] is True
        assert result["data"]["automator_reconnected"] is True
        # invalidate 必须在健康检查之前调用（过滤掉 CDP 采集的调用）
        non_cdp_order = [c for c in call_order if c[0] != "health_check" or len(call_order) == 1]
        # 验证 invalidate 存在且在 health_check 之前
        inv_idx = next(i for i, c in enumerate(call_order) if c[0] == "invalidate")
        hc_indices = [i for i, c in enumerate(call_order) if c[0] == "health_check"]
        # 第二次 health_check（ui_debug.js）应在 invalidate 之后
        assert any(idx > inv_idx for idx in hc_indices)


@pytest.mark.asyncio
async def test_compile_reconnect_even_if_invalidate_fails(set_env_vars):
    """invalidate 失败不应阻止健康检查重连。"""
    fake_cli_result = {"success": True, "stdout": "", "stderr": ""}
    fake_health = {"success": True, "data": {"pages": []}}
    with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli_result), \
         patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
         patch("wechat_devtools_mcp.tools.build.invalidate_connection", new_callable=AsyncMock, side_effect=Exception("invalidate error")), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=fake_health), \
         patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
        mock_socket.create_connection.return_value = MagicMock()

        params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
        result = json.loads(await wechat_build(params))

        # invalidate 异常会导致整个 try 块失败，reconnected 为 False
        assert result["success"] is True
