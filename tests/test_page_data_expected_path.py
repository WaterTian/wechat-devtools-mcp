"""page_data expected_path 参数透传测试。"""
import json
import pytest
from unittest.mock import patch, AsyncMock

from wechat_devtools_mcp.tools.automator import wechat_automator
from wechat_devtools_mcp.models.schemas import WechatAutomatorInput


@pytest.mark.asyncio
async def test_page_data_passes_expected_path(set_env_vars):
    """expected_path 应透传给 ui_debug.js 的 --expected-path 参数。"""
    fake_result = {"success": True, "path": "pages/detail/detail", "data": {"id": "123"}}
    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatAutomatorInput(
            action="page_data", auto_port=9420,
            expected_path="pages/detail/detail"
        )
        result = json.loads(await wechat_automator(params))

        assert result["success"] is True
        call_args = mock_run.call_args[0]
        assert "--expected-path" in call_args
        idx = call_args.index("--expected-path")
        assert call_args[idx + 1] == "pages/detail/detail"


@pytest.mark.asyncio
async def test_page_data_without_expected_path(set_env_vars):
    """不传 expected_path 时不加 --expected-path 参数。"""
    fake_result = {"success": True, "path": "pages/index/index", "data": {}}
    with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatAutomatorInput(action="page_data", auto_port=9420)
        result = json.loads(await wechat_automator(params))

        assert result["success"] is True
        call_args = mock_run.call_args[0]
        assert "--expected-path" not in call_args
