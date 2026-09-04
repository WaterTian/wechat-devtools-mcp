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
    async def test_windows_polls_tasklist_until_image_gone(self, monkeypatch, tmp_path):
        """Windows：按主程序镜像名 tasklist 轮询（真机 2026-09-04 前 exited 恒为 null）。"""
        monkeypatch.setattr(sys, "platform", "win32")
        root = tmp_path / "微信web开发者工具"
        (root / "resources" / "app.asar.unpacked").mkdir(parents=True)
        (root / "resources" / "app.asar.unpacked" / "package.json").write_text("{}", encoding="utf-8")
        (root / "微信开发者工具.exe").write_bytes(b"MZ")
        (root / "cli.bat").write_text("@echo off", encoding="utf-8")
        monkeypatch.setattr(ide, "CLI_PATH", str(root / "cli.bat"))
        calls = []

        class _R:
            def __init__(self, out): self.stdout = out; self.returncode = 0

        def fake_run(args, **kw):
            calls.append(args)
            # 第一次 tasklist 还有进程，第二次没了
            n = sum(1 for c in calls if c[0] == "tasklist")
            # /FO CSV：命中行以引号开头；提示行（中文/英文均可能）不以引号开头
            return _R('"微信开发者工具.exe","1234","Console","1","100 K"' if n == 1 else "信息: 没有运行的任务匹配指定标准。")

        monkeypatch.setattr(ide.subprocess, "run", fake_run)
        with patch("wechat_devtools_mcp.tools.ide._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": ""}), \
             patch("wechat_devtools_mcp.tools.ide.asyncio.sleep", new_callable=AsyncMock):
            data = json.loads(await ide._action_quit(WechatIdeInput(action="quit")))

        assert data["data"]["exited"] is True
        tl = [c for c in calls if c[0] == "tasklist"]
        assert len(tl) == 2 and "IMAGENAME eq 微信开发者工具.exe" in tl[0] and "CSV" in tl[0]

    @pytest.mark.asyncio
    async def test_windows_unknown_layout_reports_unknown(self, monkeypatch):
        """Windows 布局探测不到主程序时仍返回 None，不抛错。"""
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", r"C:\__nonexistent__\cli.bat")
        monkeypatch.setattr(ide.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "", "returncode": 0})())
        with patch("wechat_devtools_mcp.tools.ide._run_cli", new_callable=AsyncMock,
                   return_value={"success": True, "stdout": "", "stderr": ""}), \
             patch("wechat_devtools_mcp.tools.ide.asyncio.sleep", new_callable=AsyncMock):
            data = json.loads(await ide._action_quit(WechatIdeInput(action="quit")))
        # 未知布局回退到旧字符串替换，镜像名 wechatdevtools.exe，tasklist 查不到 → 视为已退出
        assert data["data"]["exited"] is True


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


class TestWindowsImageRunningCodepageSafe:
    """tasklist 输出按行首引号判定，中文/英文提示、GBK 乱码都不影响。"""

    def test_csv_row_means_running(self, monkeypatch):
        monkeypatch.setattr(ide.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": '"��.exe","4321","Console","1","1,000 K"\r\n'})())
        assert ide._windows_image_running("微信开发者工具.exe") is True

    def test_info_line_means_gone(self, monkeypatch):
        for msg in ("信息: 没有运行的任务匹配指定标准。", "INFO: No tasks are running which match the specified criteria.", "��: ��"):
            monkeypatch.setattr(ide.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": msg + "\r\n"})())
            assert ide._windows_image_running("微信开发者工具.exe") is False

    def test_probe_failure_counts_as_running(self, monkeypatch):
        def boom(*a, **k): raise OSError("no tasklist")
        monkeypatch.setattr(ide.subprocess, "run", boom)
        assert ide._windows_image_running("x.exe") is True
