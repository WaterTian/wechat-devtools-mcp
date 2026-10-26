"""顺带修复（2026-10-26）：

- compile / inspector(cdp) / navigate 在 CDP 端口被别的浏览器占着时不再把别人的页面日志当小程序日志
- status 报 project_window_open（项目窗口是否活着）与 skill_version（项目内 skill 副本是否与 MCP 一致）
- node_bridge 失败分支透传 handler 的 code（此前只留 error / hint，PR #12 的错误码就是这样被吞掉的）
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wechat_devtools_mcp.core import cdp_port as cp
from wechat_devtools_mcp.models.schemas import (
    WechatBuildInput, WechatInspectorInput, WechatNavigateInput,
)
from wechat_devtools_mcp.tools import build, ide, inspector, navigate

FOREIGN = {"listening": True, "kind": "foreign", "browser": "Chrome/156", "sample": ["page https://chatgpt.com/"], "miniprogram_targets": 0}
IDE_OPEN = {"listening": True, "kind": "ide", "browser": "Chrome/136", "sample": ["webview http://127.0.0.1:1/__pageframe__/pages/a/index"], "miniprogram_targets": 2}
IDE_SHELL = {"listening": True, "kind": "ide", "browser": "Chrome/136", "sample": ["page file:///x/app.asar/html/electron-entrance.html"], "miniprogram_targets": 0}
NONE = {"listening": False, "kind": "none", "browser": None, "sample": [], "miniprogram_targets": 0}


class TestInspectorGuard:

    @pytest.mark.asyncio
    async def test_foreign_occupant_fails_without_capturing(self):
        with patch("wechat_devtools_mcp.tools.inspector._inspect_cdp_port", return_value=FOREIGN), \
             patch("wechat_devtools_mcp.tools.inspector._run_node_script", new_callable=AsyncMock) as run:
            r = json.loads(await inspector.wechat_inspector(WechatInspectorInput(action="cdp", duration=1, cdp_port=9222)))
        assert r["success"] is False
        assert "9222" in r["message"] and "Chrome/156" in r["message"]
        assert "cdp_port=9333" in r["hint"]
        assert run.await_count == 0

    @pytest.mark.asyncio
    async def test_ide_occupant_captures(self):
        with patch("wechat_devtools_mcp.tools.inspector._inspect_cdp_port", return_value=IDE_OPEN), \
             patch("wechat_devtools_mcp.tools.inspector._run_node_script", new_callable=AsyncMock,
                   return_value={"success": True, "data": []}) as run:
            r = json.loads(await inspector.wechat_inspector(WechatInspectorInput(action="cdp", duration=1, cdp_port=9333)))
        assert r["success"] is True and run.await_count == 1


class TestCompileGuard:

    @pytest.mark.asyncio
    async def test_foreign_occupant_skips_wxml_capture(self, set_env_vars):
        cli_ok = {"success": True, "stdout": "", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=cli_ok), \
             patch("wechat_devtools_mcp.tools.build.socket") as sock, \
             patch("wechat_devtools_mcp.tools.build._inspect_cdp_port", return_value=FOREIGN), \
             patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock) as run:
            sock.create_connection.side_effect = ConnectionRefusedError
            r = json.loads(await build.wechat_build(WechatBuildInput(action="compile", project_path=str(set_env_vars), cdp_port=9222)))
        assert r["success"] is True
        assert r["data"]["wxml_errors"] == []
        assert "9222" in r["data"]["cdp_skipped"] and "Chrome/156" in r["data"]["cdp_skipped"]
        assert "⚠" in r["message"]
        assert not any("cdp_listener.js" in c.args for c in run.call_args_list)

    @pytest.mark.asyncio
    async def test_ide_occupant_captures(self, set_env_vars):
        cli_ok = {"success": True, "stdout": "", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=cli_ok), \
             patch("wechat_devtools_mcp.tools.build.socket") as sock, \
             patch("wechat_devtools_mcp.tools.build._inspect_cdp_port", return_value=IDE_OPEN), \
             patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock,
                   return_value={"success": True, "data": []}) as run:
            sock.create_connection.side_effect = ConnectionRefusedError
            r = json.loads(await build.wechat_build(WechatBuildInput(action="compile", project_path=str(set_env_vars), cdp_port=9333)))
        assert r["success"] is True and "cdp_skipped" not in r["data"]
        assert any(c.args[:3] == ("cdp_listener.js", "3", "9333") for c in run.call_args_list)


class TestNavigateGuard:

    @pytest.mark.asyncio
    async def test_foreign_occupant_navigates_without_cdp(self):
        fake = {"success": True, "cdp_logs": [], "cdp_available": False, "current_page": {"path": "pages/a/index"}}
        with patch("wechat_devtools_mcp.tools.navigate._inspect_cdp_port", return_value=FOREIGN), \
             patch("wechat_devtools_mcp.tools.navigate._run_node_script", new_callable=AsyncMock, return_value=fake) as run:
            r = json.loads(await navigate.wechat_navigate(WechatNavigateInput(page_path="pages/a/index", cdp_port=9222)))
        assert r["success"] is True
        args = run.call_args.args
        assert args[args.index("--cdp-port") + 1] == "0", "外来端口不该连，交给 JS 按 CDP 不可用处理"
        assert "9222" in r["data"]["cdp_warning"]
        assert "⚠" in r["message"]


class TestStatusWindowAndSkill:

    async def _status(self, monkeypatch, occupant, project_dir=None, skill_version=None):
        if project_dir is not None:
            monkeypatch.setattr(ide, "DEFAULT_PROJECT_PATH", str(project_dir))
            if skill_version:
                d = project_dir / ".agents" / "skills" / "wechat-devtools"
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(f"---\nname: wechat-devtools\nversion: {skill_version}\ndescription: x\n---\n# t\n", encoding="utf-8")
        monkeypatch.setattr(ide, "_inspect_cdp_port", lambda port: occupant)
        with patch("wechat_devtools_mcp.tools.ide._check_node_available", new_callable=AsyncMock, return_value=(True, "/usr/bin/node")), \
             patch("wechat_devtools_mcp.tools.ide._probe_official_mcp", new_callable=AsyncMock, return_value=None):
            return json.loads(await ide._action_status())

    @pytest.mark.asyncio
    async def test_window_open_true_when_miniprogram_targets(self, monkeypatch):
        r = await self._status(monkeypatch, IDE_OPEN)
        assert r["data"]["project_window_open"] is True

    @pytest.mark.asyncio
    async def test_window_open_false_when_only_shell(self, monkeypatch):
        r = await self._status(monkeypatch, IDE_SHELL)
        assert r["data"]["project_window_open"] is False

    @pytest.mark.asyncio
    async def test_window_open_unknown_when_no_ide_on_port(self, monkeypatch):
        assert (await self._status(monkeypatch, FOREIGN))["data"]["project_window_open"] is None
        assert (await self._status(monkeypatch, NONE))["data"]["project_window_open"] is None

    @pytest.mark.asyncio
    async def test_skill_version_mismatch_hint(self, monkeypatch, tmp_path):
        r = await self._status(monkeypatch, NONE, project_dir=tmp_path, skill_version="0.9.16")
        assert r["data"]["skill_version"] == "0.9.16"
        assert "0.9.16" in r["message"] and "不一致" in r["message"]

    @pytest.mark.asyncio
    async def test_skill_version_match_is_quiet(self, monkeypatch, tmp_path):
        from wechat_devtools_mcp import __version__
        r = await self._status(monkeypatch, NONE, project_dir=tmp_path, skill_version=__version__)
        assert r["data"]["skill_version"] == __version__
        assert "不一致" not in r["message"]

    @pytest.mark.asyncio
    async def test_skill_missing_is_none(self, monkeypatch, tmp_path):
        r = await self._status(monkeypatch, NONE, project_dir=tmp_path)
        assert r["data"]["skill_version"] is None


class TestInspectCdpPortCountsTargets:

    def test_counts_miniprogram_targets(self, monkeypatch):
        targets = [
            {"type": "webview", "url": "http://127.0.0.1:1/__pageframe__/pages/a/index"},
            {"type": "webview", "url": "http://127.0.0.1:1/appservice/s0/x/mainframe"},
            {"type": "page", "url": "file:///x/app.asar/html/electron-project.html"},
        ]
        monkeypatch.setattr(ide, "_port_listening", lambda p: True)
        monkeypatch.setattr(ide, "_http_get_json", lambda port, path, timeout: {"Browser": "Chrome/136"} if path == "/json/version" else targets)
        occ = ide._inspect_cdp_port(9333)
        assert occ["kind"] == "ide" and occ["miniprogram_targets"] == 2


@pytest.mark.asyncio
async def test_node_bridge_reader_passes_handler_code():
    """daemon 的失败响应里 handler 给的 code 要透传给调用方。"""
    from wechat_devtools_mcp.core import node_bridge as nb
    lines = [json.dumps({"id": 7, "success": False, "data": {
        "success": False, "code": "CDP_UNAVAILABLE", "error": "ECONNREFUSED", "hint": "换端口",
    }}).encode() + b"\n", b""]

    class _Stdout:
        async def readline(self):
            return lines.pop(0)

    class _Proc:
        returncode = None
        stdout = _Stdout()

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    old_proc = nb._daemon_process
    nb._daemon_process = _Proc()
    nb._pending_responses[7] = fut
    try:
        await nb._response_reader()
    finally:
        nb._daemon_process = old_proc
        nb._pending_responses.pop(7, None)
    assert fut.result() == {"success": False, "error": "ECONNREFUSED", "hint": "换端口", "code": "CDP_UNAVAILABLE"}
