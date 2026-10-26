"""call_wx 对同步 wx API 的处理（2026-10-26 真机复测 P8 ①）。"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import WechatAutomatorInput
from wechat_devtools_mcp.tools.automator import wechat_automator


@pytest.mark.asyncio
async def test_sync_flag_and_message_pass_through():
    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock,
               return_value={"success": True, "method": "getWindowInfo", "returnValue": {"pixelRatio": 3}, "sync": True}):
        r = json.loads(await wechat_automator(WechatAutomatorInput(action="call_wx", method="getWindowInfo")))
    assert r["success"] is True
    assert r["data"]["sync"] is True and r["data"]["return_value"] == {"pixelRatio": 3}
    assert "evaluate" in r["message"]


@pytest.mark.asyncio
async def test_async_result_has_no_sync_flag():
    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock,
               return_value={"success": True, "method": "getNetworkType", "returnValue": {"networkType": "wifi"}}):
        r = json.loads(await wechat_automator(WechatAutomatorInput(action="call_wx", method="getNetworkType")))
    assert r["success"] is True and "sync" not in r["data"]


@pytest.mark.asyncio
async def test_timeout_hints_evaluate_for_sync_apis():
    """白名单外的同步 API 仍会超时：hint 必须指向 evaluate 直调。"""
    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock,
               return_value={"success": False, "error": "timeout waiting for automator response"}):
        r = json.loads(await wechat_automator(WechatAutomatorInput(action="call_wx", method="getSomethingInfo")))
    assert r["success"] is False
    assert "evaluate" in r["hint"] and "getSomethingInfo" in r["hint"]
