"""screenshot 诊断字段透传测试。

背景：screenshot.js 早就在返回 isScrollViewPage / fixedHeader / fixedFooter，
SKILL.md 也写明「scroll-view 页面会返回 isScrollViewPage: true」，
但 Python 侧的 _ok() 只挑了 path/width/height/segments 四个字段，
其余全部被丢弃——与 v0.9.15 修掉的「CDP 恒返回 0 条」是同一类缺陷：
JS 产出了数据，Python 读不到。
"""
import json
import pytest
from unittest.mock import patch, AsyncMock

from wechat_devtools_mcp.tools.screenshot import wechat_screenshot
from wechat_devtools_mcp.models.schemas import WechatScreenshotInput


class TestScrollViewPassthrough:
    """scroll-view 页面无法拼长图，必须让调用方知道拿到的只是一屏。"""

    @pytest.mark.asyncio
    async def test_is_scroll_view_page_reaches_caller(self, set_env_vars):
        fake = {
            "success": True, "path": "/tmp/test.png",
            "width": 375, "height": 667, "segments": 1,
            "isScrollViewPage": True,
        }
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["success"] is True
        assert data["data"]["is_scroll_view_page"] is True

    @pytest.mark.asyncio
    async def test_scroll_view_warning_in_message(self, set_env_vars):
        """仅返回字段不够——message 里要明说这只是一屏，否则 AI 会当成完整长图。"""
        fake = {
            "success": True, "path": "/tmp/test.png",
            "width": 375, "height": 667, "segments": 1,
            "isScrollViewPage": True,
        }
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert "scroll-view" in data["message"]

    @pytest.mark.asyncio
    async def test_normal_page_has_no_scroll_view_flag(self, set_env_vars):
        """普通页面不应出现该字段，避免噪音。"""
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 2000, "segments": 4}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert "is_scroll_view_page" not in data["data"]


class TestStitchDiagnostics:
    """拼接质量诊断：固定区域高度、被截断、内容缺口。"""

    @pytest.mark.asyncio
    async def test_fixed_regions_passed_through(self, set_env_vars):
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 2000, "segments": 4,
                "fixedHeader": 132, "fixedFooter": 150}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["data"]["fixed_header"] == 132
        assert data["data"]["fixed_footer"] == 150

    @pytest.mark.asyncio
    async def test_truncated_page_warns(self, set_env_vars):
        """超过分段上限时必须告警，否则「拍全了」是假的。"""
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 20000, "segments": 30,
                "truncated": True}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["data"]["truncated"] is True
        assert "截断" in data["message"]

    @pytest.mark.asyncio
    async def test_content_gaps_warn(self, set_env_vars):
        """固定区域吃光重叠会导致内容丢失，必须如实上报而不是假装拼好了。"""
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 2000, "segments": 4,
                "contentGaps": 2}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["data"]["content_gaps"] == 2
        assert "缺口" in data["message"]


class TestDetectionConfidence:
    """固定区域测不准时必须明说，不能让调用方以为拼接是准的。"""

    @pytest.mark.asyncio
    async def test_low_confidence_warns(self, set_env_vars):
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 2000, "segments": 3,
                "detectionConfident": False}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["data"]["detection_confident"] is False
        assert "未能可靠识别" in data["message"]

    @pytest.mark.asyncio
    async def test_confident_stays_quiet(self, set_env_vars):
        """检测可靠时不应产生噪音字段与告警。"""
        fake = {"success": True, "path": "/tmp/test.png",
                "width": 375, "height": 2000, "segments": 3,
                "detectionConfident": True, "fixedHeader": 120}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert "detection_confident" not in data["data"]
        assert "⚠" not in data["message"]


class TestFailureHint:
    """JS 失败时给的 hint 是排障关键（issue #5 的 /index 提示就走这条路）。"""

    @pytest.mark.asyncio
    async def test_hint_preserved_on_failure(self, set_env_vars):
        fake = {
            "success": False,
            "error": "跳转失败：期望 pages/foo，实际停留在 pages/index/index",
            "hint": "提示：末尾可能需要 /index（如 pages/foo/index）",
        }
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, return_value=fake):
            data = json.loads(await wechat_screenshot(
                WechatScreenshotInput(output_path="/tmp/test.png")))

        assert data["success"] is False
        assert "/index" in data.get("hint", "")
