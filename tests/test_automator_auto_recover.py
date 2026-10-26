"""automator 失联自动恢复（2026-10-26）。

真机：项目窗口被关（SessionEnd 钩子 / 手动）或 automator 闲置后，9420 在听却不应答，
`start`（cli auto）一次即活、约 7s。此前每个动作只报「Failed connecting」，agent 得自己走
start → 重试，现场甚至固定成 close → open → start。现：automator 动作 / navigate / screenshot
遇连接类失败自动 start 一次并重试，返回 auto_recovered。
有副作用的动作（tap / input / call_method …）只在「连接阶段」失败时重试；
动作执行中断线或超时不重试，避免重复触发。
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import (
    WechatAutomatorInput, WechatNavigateInput, WechatScreenshotInput,
)
from wechat_devtools_mcp.tools import automator, navigate, screenshot
from wechat_devtools_mcp.utils.response import _ok

CONNECT_FAIL = {"success": False, "error": "Failed connecting to ws://localhost:9420, check if target project window is opened with automation enabled"}
NOT_READY = {"success": False, "error": "连接失败: Connection not ready: health check failed after connect"}
MID_CLOSED = {"success": False, "error": "Connection closed, check if wechat web devTools is still running"}
TIMEOUT = {"success": False, "error": "daemon 响应超时（30秒）"}
OTHER = {"success": False, "error": "元素未找到: .nope"}
PAGE_OK = {"success": True, "path": "pages/a/index", "data": {"x": 1}}
START_OK = _ok({"port": 9420, "verified": True, "ready_after_ms": 7000, "cli_attempts": 1}, message="ok")
START_BAD = _ok({"port": 9420, "verified": False, "retry_after_ms": 3000}, message="not ready")


async def _run(action="page_data", results=(), start=START_OK, **kw):
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, side_effect=list(results)) as run, \
         patch("wechat_devtools_mcp.tools.automator._action_start",
               new_callable=AsyncMock, return_value=start) as st:
        r = json.loads(await automator.wechat_automator(WechatAutomatorInput(action=action, **kw)))
    return r, run, st


class TestAutomatorActions:

    @pytest.mark.asyncio
    async def test_page_data_recovers_after_connect_failure(self):
        r, run, st = await _run(results=[CONNECT_FAIL, PAGE_OK])
        assert r["success"] is True
        assert r["data"]["auto_recovered"]["ready_after_ms"] == 7000
        assert "自动恢复" in r["message"]
        assert run.await_count == 2 and st.await_count == 1

    @pytest.mark.asyncio
    async def test_page_data_recovers_after_health_check_exhausted(self):
        r, run, st = await _run(results=[NOT_READY, PAGE_OK])
        assert r["success"] is True and st.await_count == 1

    @pytest.mark.asyncio
    async def test_read_only_action_retries_after_timeout(self):
        r, run, st = await _run(results=[TIMEOUT, PAGE_OK])
        assert r["success"] is True and run.await_count == 2

    @pytest.mark.asyncio
    async def test_side_effect_action_recovers_only_on_connect_phase_failure(self):
        r, run, st = await _run(action="tap", selector=".btn", results=[CONNECT_FAIL, {"success": True}])
        assert r["success"] is True and run.await_count == 2 and st.await_count == 1

    @pytest.mark.asyncio
    async def test_side_effect_action_not_retried_after_mid_action_disconnect(self):
        r, run, st = await _run(action="tap", selector=".btn", results=[MID_CLOSED])
        assert r["success"] is False
        assert run.await_count == 1 and st.await_count == 0

    @pytest.mark.asyncio
    async def test_side_effect_action_not_retried_after_timeout(self):
        r, run, st = await _run(action="call_method", method="submit", results=[TIMEOUT])
        assert r["success"] is False and run.await_count == 1 and st.await_count == 0

    @pytest.mark.asyncio
    async def test_no_retry_when_start_not_verified(self):
        r, run, st = await _run(results=[CONNECT_FAIL], start=START_BAD)
        assert r["success"] is False
        assert run.await_count == 1 and st.await_count == 1
        assert "hint" in r  # 原有恢复提示保留

    @pytest.mark.asyncio
    async def test_non_connection_failure_untouched(self):
        r, run, st = await _run(action="element_info", selector=".x", results=[OTHER])
        assert r["success"] is False and run.await_count == 1 and st.await_count == 0

    @pytest.mark.asyncio
    async def test_start_itself_never_recurses(self):
        with patch("wechat_devtools_mcp.tools.automator._action_start",
                   new_callable=AsyncMock, return_value=json.dumps({"success": False, "error_code": "UNKNOWN_ERROR", "message": "CLI auto 执行失败"})) as st:
            r = json.loads(await automator.wechat_automator(WechatAutomatorInput(action="start", project_path="D:/p")))
        assert r["success"] is False and st.await_count == 1


class TestNavigate:

    @pytest.mark.asyncio
    async def test_navigate_recovers(self):
        ok = {"success": True, "cdp_logs": [], "cdp_available": False, "current_page": {"path": "pages/a/index"}}
        with patch("wechat_devtools_mcp.tools.navigate._run_node_script",
                   new_callable=AsyncMock, side_effect=[CONNECT_FAIL, ok]) as run, \
             patch("wechat_devtools_mcp.tools.navigate._try_recover_automator",
                   new_callable=AsyncMock, return_value={"ready_after_ms": 6500}) as rec:
            r = json.loads(await navigate.wechat_navigate(WechatNavigateInput(page_path="pages/a/index")))
        assert r["success"] is True
        assert r["data"]["auto_recovered"]["ready_after_ms"] == 6500
        assert run.await_count == 2 and rec.await_count == 1

    @pytest.mark.asyncio
    async def test_navigate_gives_up_when_recovery_fails(self):
        with patch("wechat_devtools_mcp.tools.navigate._run_node_script",
                   new_callable=AsyncMock, side_effect=[CONNECT_FAIL]) as run, \
             patch("wechat_devtools_mcp.tools.navigate._try_recover_automator",
                   new_callable=AsyncMock, return_value=None):
            r = json.loads(await navigate.wechat_navigate(WechatNavigateInput(page_path="pages/a/index")))
        assert r["success"] is False and run.await_count == 1


class TestScreenshot:

    @pytest.mark.asyncio
    async def test_screenshot_recovers(self, tmp_path):
        out = tmp_path / "s.png"; out.write_bytes(b"x")
        ok = {"success": True, "path": str(out), "width": 1, "height": 1, "segments": 1}
        with patch("wechat_devtools_mcp.tools.screenshot._run_node_script",
                   new_callable=AsyncMock, side_effect=[CONNECT_FAIL, ok]) as run, \
             patch("wechat_devtools_mcp.tools.screenshot._try_recover_automator",
                   new_callable=AsyncMock, return_value={"ready_after_ms": 7100}):
            r = json.loads(await screenshot.wechat_screenshot(WechatScreenshotInput(output_path=str(out))))
        assert r["success"] is True
        assert r["data"]["auto_recovered"]["ready_after_ms"] == 7100
        assert run.await_count == 2


def test_down_detection():
    assert automator._automator_down("Failed connecting to ws://localhost:9420") == "connect"
    assert automator._automator_down("连接失败: health_check_timeout") == "connect"
    assert automator._automator_down("daemon 响应超时（30秒）") == "mid"
    assert automator._automator_down("Connection closed, check if wechat web devTools is still running") == "mid"
    assert automator._automator_down("元素未找到") is None
    assert automator._automator_down(json.dumps({"success": False, "message": "跳转失败：Failed connecting to ws://localhost:9420"})) == "connect"
    assert automator._automator_down(json.dumps({"success": True, "message": "Failed connecting to ws://"})) is None
