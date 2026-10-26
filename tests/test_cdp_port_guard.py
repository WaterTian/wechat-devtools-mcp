"""CDP 端口三件事（2026-10-26，源自 FanTown 真实使用）：

1. 占用者识别：9222 被本机常驻 sbot 的 Chrome 长期占用。`open` 此前只看 TCP 是否监听，
   Chrome 在听就当 IDE 就绪，然后把 Chrome 页面的报错当成小程序启动错误返回
   （会话日志：「IDE 启动报 10 个错，全是阿里云/百度页面」）。
2. 会话内粘性：agent 固定用 9333，但 inspector / navigate / compile 漏传 cdp_port 就连到 Chrome。
3. 环境变量默认值 WECHAT_CDP_PORT。
"""
import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.core import cdp_port as cp
from wechat_devtools_mcp.models.schemas import (
    WechatBuildInput, WechatIdeInput, WechatInspectorInput, WechatNavigateInput,
)
from wechat_devtools_mcp.tools import ide, inspector


CHROME_VERSION = {"Browser": "Chrome/156.0.8078.47"}
CHROME_TARGETS = [
    {"type": "page", "url": "https://chatgpt.com/settings/usage?tab=overview", "title": "Usage"},
    {"type": "iframe", "url": "https://cdn.platform.openai.com/deployments/dil/v14/runner.html"},
    {"type": "browser_ui", "url": "chrome://omnibox-popup.top-chrome/"},
    {"type": "background_page", "url": "chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/offscreen.html"},
]
IDE2_TARGETS = [
    {"type": "webview", "url": "http://127.0.0.1:16587/__pageframe__/pages/home/index", "title": "小程序渲染层"},
    {"type": "webview", "url": "devtools://devtools/bundled/devtools_app.html?remoteBase=x"},
    {"type": "iframe", "url": "chrome-extension://ancjdafmchkhkhohigofkchmokpinace/devtools/devtools.html"},
    {"type": "webview", "url": "http://127.0.0.1:16587/appservice/s0/_sessionId/sim/mainframe", "title": "小程序逻辑层"},
]
IDE2_SHELL_ONLY = [{"type": "page", "url": "file:///Applications/x.app/Contents/Resources/app.asar/html/electron-entrance.html"}]
IDE1_TARGETS = [{"type": "webview", "url": "http://127.0.0.1:50000/appservice/mainframe"}]


@pytest.fixture(autouse=True)
def _reset_session_port():
    cp.forget_cdp_port()
    yield
    cp.forget_cdp_port()


class TestClassify:

    def test_ide2_targets(self):
        assert cp.classify_cdp_targets(IDE2_TARGETS) == "ide"

    def test_ide2_shell_only_counts_as_ide(self):
        assert cp.classify_cdp_targets(IDE2_SHELL_ONLY) == "ide"

    def test_ide1_targets(self):
        assert cp.classify_cdp_targets(IDE1_TARGETS) == "ide"

    def test_chrome_is_foreign(self):
        assert cp.classify_cdp_targets(CHROME_TARGETS) == "foreign"

    def test_empty_or_garbage(self):
        assert cp.classify_cdp_targets([]) == "empty"
        assert cp.classify_cdp_targets(None) == "empty"
        assert cp.classify_cdp_targets("nope") == "empty"


class TestResolve:

    def test_explicit_wins_over_session(self):
        cp.remember_cdp_port(9333)
        assert cp.resolve_cdp_port(WechatInspectorInput(action="cdp", cdp_port=9222)) == 9222

    def test_session_port_sticks_when_not_passed(self):
        cp.remember_cdp_port(9333)
        assert cp.resolve_cdp_port(WechatInspectorInput(action="cdp")) == 9333
        assert cp.resolve_cdp_port(WechatNavigateInput(page_path="pages/a/index")) == 9333
        assert cp.resolve_cdp_port(WechatBuildInput(action="compile")) == 9333
        assert cp.resolve_cdp_port(WechatIdeInput(action="open")) == 9333

    def test_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr(cp, "DEFAULT_CDP_PORT", 9444)
        assert cp.resolve_cdp_port(WechatInspectorInput(action="cdp")) == 9444


def _open_harness(monkeypatch, *, listening: bool, targets, popen_calls, kill_calls):
    """驱动 _action_open 到「是否要 kill IDE」那一步为止。"""
    import subprocess
    monkeypatch.setattr(sys, "platform", "darwin")
    electron = "/Applications/wechatwebdevtools.app/Contents/MacOS/Electron"
    monkeypatch.setattr(ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli")
    monkeypatch.setattr(ide.os.path, "exists", lambda p: p == electron)
    monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "Electron")
    monkeypatch.setattr(ide, "DEFAULT_PROJECT_PATH", "/Users/test/proj")

    class _Proc:
        returncode = None
        def poll(self): return None

    def fake_get_json(port, path, timeout):
        if path == "/json/version":
            return CHROME_VERSION if targets is CHROME_TARGETS else {"Browser": "Chrome/136.0.7103.177"}
        return targets

    async def fake_kill(pattern): kill_calls.append(pattern)
    async def _ok_ready(port, timeout=60, **kw): return True, True
    async def fake_targets(port, timeout=8.0, interval=0.5): return True
    async def fake_node(*a, **k): return {"success": True, "data": []}
    async def fake_cli(*a, **k): return {"success": True, "stdout": "", "stderr": ""}
    async def _noop(*a, **k): return None

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (popen_calls.append(a), _Proc())[1])
    monkeypatch.setattr(ide, "_port_listening", lambda p: listening)
    monkeypatch.setattr(ide, "_http_get_json", fake_get_json)
    monkeypatch.setattr(ide, "_kill_existing_ide", fake_kill)
    monkeypatch.setattr(ide, "_wait_ide_ready", _ok_ready)
    monkeypatch.setattr(ide, "_wait_miniprogram_targets", fake_targets)
    monkeypatch.setattr(ide, "_run_node_script", fake_node)
    monkeypatch.setattr(ide, "_run_cli", fake_cli)
    monkeypatch.setattr(asyncio, "sleep", _noop)


class TestOpenGuardsForeignOccupant:

    @pytest.mark.asyncio
    async def test_foreign_browser_on_port_fails_fast_without_killing_ide(self, monkeypatch):
        popen_calls, kill_calls = [], []
        _open_harness(monkeypatch, listening=True, targets=CHROME_TARGETS,
                      popen_calls=popen_calls, kill_calls=kill_calls)
        r = json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9222)))

        assert r["success"] is False
        assert "9222" in r["message"] and "占用" in r["message"]
        assert "Chrome/156" in r["message"]
        assert "9333" in r["hint"] and "WECHAT_CDP_PORT" in r["hint"]
        assert r["cdp_port_occupant"]["kind"] == "foreign"
        assert kill_calls == [], "端口被别人占着就不该去杀 IDE"
        assert popen_calls == []
        assert cp.session_cdp_port() is None

    @pytest.mark.asyncio
    async def test_previous_ide_on_port_proceeds_and_remembers_port(self, monkeypatch):
        popen_calls, kill_calls = [], []
        _open_harness(monkeypatch, listening=True, targets=IDE2_TARGETS,
                      popen_calls=popen_calls, kill_calls=kill_calls)
        r = json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9333)))

        assert r["success"] is True, r
        assert len(kill_calls) == 1 and len(popen_calls) == 1
        assert cp.session_cdp_port() == 9333

    @pytest.mark.asyncio
    async def test_port_free_proceeds(self, monkeypatch):
        popen_calls, kill_calls = [], []
        _open_harness(monkeypatch, listening=False, targets=[],
                      popen_calls=popen_calls, kill_calls=kill_calls)
        r = json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9333)))
        assert r["success"] is True, r
        assert cp.session_cdp_port() == 9333

    @pytest.mark.asyncio
    async def test_reopen_without_port_reuses_session_port(self, monkeypatch):
        popen_calls, kill_calls = [], []
        cp.remember_cdp_port(9333)
        _open_harness(monkeypatch, listening=False, targets=[],
                      popen_calls=popen_calls, kill_calls=kill_calls)
        r = json.loads(await ide._action_open(WechatIdeInput(action="open")))
        assert r["success"] is True, r
        assert r["data"]["cdp_port"] == 9333
        assert any("--remote-debugging-port=9333" in str(c) for c in popen_calls)


class TestInspectorUsesSessionPort:

    @pytest.mark.asyncio
    async def test_cdp_action_without_port_uses_remembered(self):
        cp.remember_cdp_port(9333)
        with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
                   new_callable=AsyncMock, return_value={"success": True, "data": []}) as run:
            r = json.loads(await inspector.wechat_inspector(WechatInspectorInput(action="cdp", duration=1)))
        assert r["success"] is True
        assert run.call_args.args[:3] == ("cdp_listener.js", "1", "9333")

    @pytest.mark.asyncio
    async def test_cdp_action_explicit_port_wins(self):
        cp.remember_cdp_port(9333)
        with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
                   new_callable=AsyncMock, return_value={"success": True, "data": []}) as run:
            await inspector.wechat_inspector(WechatInspectorInput(action="cdp", duration=1, cdp_port=9223))
        assert run.call_args.args[2] == "9223"


class TestStatusReportsOccupant:

    @pytest.mark.asyncio
    async def test_status_flags_foreign_occupant(self, monkeypatch):
        monkeypatch.setattr(ide, "_port_listening", lambda p: True)
        monkeypatch.setattr(ide, "_http_get_json",
                            lambda port, path, timeout: CHROME_VERSION if path == "/json/version" else CHROME_TARGETS)
        with patch("wechat_devtools_mcp.tools.ide._check_node_available",
                   new_callable=AsyncMock, return_value=(True, "/usr/bin/node")), \
             patch("wechat_devtools_mcp.tools.ide._probe_official_mcp",
                   new_callable=AsyncMock, return_value=None):
            r = json.loads(await ide._action_status())
        d = r["data"]
        assert d["cdp_port"] == cp.DEFAULT_CDP_PORT
        assert d["cdp_port_session"] is None
        assert d["cdp_port_occupant"]["kind"] == "foreign"
        assert "WECHAT_CDP_PORT" in r["message"]

    @pytest.mark.asyncio
    async def test_status_reports_session_port_and_ide_occupant(self, monkeypatch):
        cp.remember_cdp_port(9333)
        monkeypatch.setattr(ide, "_port_listening", lambda p: True)
        monkeypatch.setattr(ide, "_http_get_json",
                            lambda port, path, timeout: {"Browser": "Chrome/136"} if path == "/json/version" else IDE2_TARGETS)
        with patch("wechat_devtools_mcp.tools.ide._check_node_available",
                   new_callable=AsyncMock, return_value=(True, "/usr/bin/node")), \
             patch("wechat_devtools_mcp.tools.ide._probe_official_mcp",
                   new_callable=AsyncMock, return_value=None):
            r = json.loads(await ide._action_status())
        d = r["data"]
        assert d["cdp_port"] == 9333 and d["cdp_port_session"] == 9333
        assert d["cdp_port_occupant"]["kind"] == "ide"
        assert "WECHAT_CDP_PORT" not in r["message"]
