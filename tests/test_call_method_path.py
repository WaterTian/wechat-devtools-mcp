"""call_method 返回值应包含 path 字段。"""
import json
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_call_method_success_includes_path():
    """call_method 成功时应返回 path 字段。"""
    from wechat_devtools_mcp.tools.automator import _action_call_method
    from wechat_devtools_mcp.models.schemas import WechatAutomatorInput

    mock_result = {"success": True, "path": "pages/home/index", "method": "onRefresh", "returnValue": None}

    params = WechatAutomatorInput(action="call_method", method="onRefresh")

    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=mock_result):
        response = await _action_call_method(params)
        data = json.loads(response)
        assert data["success"] is True
        assert data["data"]["path"] == "pages/home/index"
        assert data["data"]["method"] == "onRefresh"


@pytest.mark.asyncio
async def test_call_method_failure_includes_path():
    """call_method 失败时错误消息应包含当前页面路径。"""
    from wechat_devtools_mcp.tools.automator import _action_call_method
    from wechat_devtools_mcp.models.schemas import WechatAutomatorInput

    mock_result = {"success": False, "error": "page.onSubmit not exists", "path": "pages/list/index"}

    params = WechatAutomatorInput(action="call_method", method="onSubmit")

    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=mock_result):
        response = await _action_call_method(params)
        data = json.loads(response)
        assert data["success"] is False
        assert "pages/list/index" in data["message"]
