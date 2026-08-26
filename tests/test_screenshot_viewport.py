"""screenshot 视口控制参数测试。"""
import json
import pytest
from unittest.mock import patch, AsyncMock

from wechat_devtools_mcp.tools.screenshot import wechat_screenshot
from wechat_devtools_mcp.models.schemas import WechatScreenshotInput


@pytest.mark.asyncio
async def test_screenshot_passes_no_full_page(set_env_vars):
    """full_page=False 应传递 --no-full-page 给 JS。"""
    fake_result = {"success": True, "path": "/tmp/test.png", "width": 375, "height": 667, "segments": 1}
    with patch("wechat_devtools_mcp.tools.screenshot._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatScreenshotInput(full_page=False, output_path="/tmp/test.png")
        await wechat_screenshot(params)
        call_args = mock_run.call_args[0]
        assert "--no-full-page" in call_args


@pytest.mark.asyncio
async def test_screenshot_passes_scroll_top(set_env_vars):
    """scroll_top 应传递 --scroll-top N 给 JS。"""
    fake_result = {"success": True, "path": "/tmp/test.png", "width": 375, "height": 667, "segments": 1}
    with patch("wechat_devtools_mcp.tools.screenshot._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatScreenshotInput(scroll_top=500, output_path="/tmp/test.png")
        await wechat_screenshot(params)
        call_args = mock_run.call_args[0]
        assert "--scroll-top" in call_args
        idx = call_args.index("--scroll-top")
        assert call_args[idx + 1] == "500"


@pytest.mark.asyncio
async def test_screenshot_default_full_page(set_env_vars):
    """默认不传 --no-full-page。"""
    fake_result = {"success": True, "path": "/tmp/test.png", "width": 375, "height": 667, "segments": 1}
    with patch("wechat_devtools_mcp.tools.screenshot._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatScreenshotInput(output_path="/tmp/test.png")
        await wechat_screenshot(params)
        call_args = mock_run.call_args[0]
        assert "--no-full-page" not in call_args
