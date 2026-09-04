"""wechat_ide open 的等待策略：按就绪信号触发，而不是固定睡眠（2026-09-03 提效）。

真机（IDE 2.02.2608060 Stable）实测 open 约 25~30s，其中固定等待占大头：
kill 后固定 2s、启动后固定 3s 轮询、健康检查前固定 5s + 采集 5s。
改为：kill 后轮询进程消失即返回；CDP 端口一监听就结束启动轮询；
健康检查等小程序 target（__pageframe__ / appservice）出现后采集 3s。
"""
import asyncio
import http.server
import json
import sys
import threading

import pytest

from wechat_devtools_mcp.tools import ide


class _JsonList(http.server.BaseHTTPRequestHandler):
    targets: list = []

    def do_GET(self):
        body = json.dumps(self.targets).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def cdp_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _JsonList)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server
    server.shutdown()


class TestWaitMiniprogramTargets:

    @pytest.mark.asyncio
    async def test_returns_true_when_appservice_target_present(self, cdp_server):
        _JsonList.targets = [
            {"type": "page", "url": "file:///Applications/wechatwebdevtools.app/.../electron-entrance.html"},
            {"type": "webview", "url": "http://127.0.0.1:39832/appservice/s0/_sessionId/x/mainframe"},
        ]
        assert await ide._wait_miniprogram_targets(cdp_server.server_port, timeout=2) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_pageframe_target(self, cdp_server):
        _JsonList.targets = [{"type": "webview", "url": "http://127.0.0.1:39832/__pageframe__/pages/index/index"}]
        assert await ide._wait_miniprogram_targets(cdp_server.server_port, timeout=2) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_only_shell(self, cdp_server):
        """只有 IDE 外壳 target（项目窗口没起来）→ 超时返回 False，不抛错。"""
        _JsonList.targets = [{"type": "page", "url": "file:///.../electron-entrance.html"}]
        assert await ide._wait_miniprogram_targets(cdp_server.server_port, timeout=0.6, interval=0.2) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_port_closed(self):
        import socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        assert await ide._wait_miniprogram_targets(port, timeout=0.5, interval=0.2) is False


class TestKillExistingIdeReturnsEarly:

    @pytest.mark.asyncio
    async def test_macos_returns_as_soon_as_process_gone(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        calls = []

        class _R:
            def __init__(self, rc): self.returncode = rc

        def fake_run(args, **kw):
            calls.append(args[0])
            # pkill 成功；随后的 pgrep 立刻报「没有进程」
            return _R(0 if args[0] == "pkill" else 1)

        slept = []

        async def fake_sleep(d):
            slept.append(d)

        monkeypatch.setattr(ide.subprocess, "run", fake_run)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await ide._kill_existing_ide("/Applications/wechatwebdevtools.app")

        assert calls[0] == "pkill" and "pgrep" in calls
        assert sum(slept) < 2, f"进程已消失仍固定等待：{slept}"


class TestOpenHealthCheckGating:

    @pytest.mark.asyncio
    async def test_open_waits_for_targets_then_captures_3s(self, monkeypatch, tmp_path):
        """健康检查：先等小程序 target，再采集 3 秒，不再固定睡 5 秒。"""
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

        waited = {}
        node_calls = []

        async def fake_wait_targets(port, timeout=8.0, interval=0.5):
            waited["port"] = port
            return True

        async def fake_node(script, *args, **kw):
            node_calls.append((script, args))
            return {"success": True, "data": []}

        async def _ok_ready(port, timeout=60): return True, True
        async def _noop(*a, **k): return None
        async def fake_cli(*a, **k): return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _Proc())
        monkeypatch.setattr(ide, "_wait_miniprogram_targets", fake_wait_targets)
        monkeypatch.setattr(ide, "_run_node_script", fake_node)
        monkeypatch.setattr(ide, "_wait_ide_ready", _ok_ready)
        monkeypatch.setattr(ide, "_kill_existing_ide", _noop)
        monkeypatch.setattr(ide, "_run_cli", fake_cli)
        monkeypatch.setattr(ide, "_port_listening", lambda p: True)
        monkeypatch.setattr(asyncio, "sleep", _noop)

        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        result = json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9223)))

        assert result["success"] is True, result
        assert waited["port"] == 9223
        assert node_calls and node_calls[0][0] == "cdp_listener.js"
        assert node_calls[0][1][0] == "3", "采集时长应为 3 秒"
