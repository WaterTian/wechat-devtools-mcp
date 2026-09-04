"""生命周期健壮性（真机 2026-09-03，IDE 2.02.2608060 Stable 发现的三个时序问题）。

1. 纯 CLI open 后立刻 start：项目窗口还没加载完，`cli auto` 打印 ✔ 却不开端口（假成功）。
   实测 open 后 3s 必失败、18s 后必成功 → start 最多重试 3 轮 cli auto。
2. `cli quit` 0.3s 返回，进程要 ~10s 才退干净 → quit 等进程消失再返回，报 exited。
3. 窗口已关时所有 automator 动作只报「Failed connecting to ws://…」无提示 → 统一附恢复 hint。
"""
import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import WechatAutomatorInput, WechatIdeInput
from wechat_devtools_mcp.tools import automator, ide


class TestStartRetriesCliAuto:

    @pytest.mark.asyncio
    async def test_second_cli_auto_succeeds(self):
        params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
        port_ready = AsyncMock(side_effect=[False, True])
        with patch("wechat_devtools_mcp.tools.automator._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "✔ auto", "stderr": "", "return_code": 0}) as cli, \
             patch("wechat_devtools_mcp.tools.automator._verify_port_ready", port_ready), \
             patch("wechat_devtools_mcp.tools.automator._verify_ws_ready", new_callable=AsyncMock, return_value=True), \
             patch("wechat_devtools_mcp.tools.automator.asyncio.sleep", new_callable=AsyncMock) as slp:
            data = json.loads(await automator._action_start(params))

        assert data["success"] is True and data["data"]["verified"] is True
        assert cli.await_count == 2, "第一轮端口没起来，应再跑一次 cli auto"
        assert data["data"]["cli_attempts"] == 2
        assert slp.await_count >= 1

    @pytest.mark.asyncio
    async def test_gives_up_after_three_rounds_with_recovery_hint(self):
        params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
        with patch("wechat_devtools_mcp.tools.automator._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": "", "return_code": 0}) as cli, \
             patch("wechat_devtools_mcp.tools.automator._verify_port_ready", new_callable=AsyncMock, return_value=False), \
             patch("wechat_devtools_mcp.tools.automator.asyncio.sleep", new_callable=AsyncMock):
            data = json.loads(await automator._action_start(params))

        assert data["success"] is False
        assert cli.await_count == 3
        assert "未监听" in data["message"]
        assert "wechat_ide(action='open'" in data["hint"]


class TestQuitWaitsForExit:

    @pytest.mark.asyncio
    async def test_reports_exited_when_processes_gone(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli")
        pgrep_calls = []

        class _R:
            def __init__(self, rc): self.returncode = rc

        def fake_run(args, **kw):
            pgrep_calls.append(args)
            return _R(1)  # 没有匹配进程

        monkeypatch.setattr(ide.subprocess, "run", fake_run)
        with patch("wechat_devtools_mcp.tools.ide._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": ""}):
            data = json.loads(await ide._action_quit(WechatIdeInput(action="quit")))

        assert data["success"] is True
        assert data["data"]["exited"] is True
        assert pgrep_calls and pgrep_calls[0][:2] == ["pgrep", "-f"]
        assert "/Applications/wechatwebdevtools.app" in pgrep_calls[0]

    @pytest.mark.asyncio
    async def test_reports_not_exited_on_timeout(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli")

        class _R:
            returncode = 0  # 一直有进程

        monkeypatch.setattr(ide.subprocess, "run", lambda *a, **k: _R())
        with patch("wechat_devtools_mcp.tools.ide._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": ""}):
            data = json.loads(await ide._action_quit(WechatIdeInput(action="quit")))

        assert data["success"] is True
        assert data["data"]["exited"] is False
        assert "仍未" in data["message"]

    @pytest.mark.asyncio
    async def test_non_macos_reports_unknown(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        with patch("wechat_devtools_mcp.tools.ide._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": ""}):
            data = json.loads(await ide._action_quit(WechatIdeInput(action="quit")))
        assert data["data"]["exited"] is None


class TestWsUnreachableHint:

    @pytest.mark.asyncio
    async def test_page_stack_failure_gets_recovery_hint(self):
        err = {"success": False, "error": "连接失败: Failed connecting to ws://localhost:9420, "
                                          "check if target project window is opened with automation enabled"}
        with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=err):
            data = json.loads(await automator.wechat_automator(WechatAutomatorInput(action="page_stack")))
        assert data["success"] is False
        assert "wechat_automator(action='start')" in data["hint"]
        assert "wechat_ide(action='open'" in data["hint"]

    @pytest.mark.asyncio
    async def test_other_failures_untouched(self):
        err = {"success": False, "error": "未知 action: xyz"}
        with patch("wechat_devtools_mcp.tools.automator._run_node_script", new_callable=AsyncMock, return_value=err):
            data = json.loads(await automator.wechat_automator(WechatAutomatorInput(action="page_stack")))
        assert data["success"] is False and "hint" not in data
