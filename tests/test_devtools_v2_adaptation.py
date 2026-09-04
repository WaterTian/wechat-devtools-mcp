"""微信开发者工具 2.x（Electron）适配测试。

背景：IDE 2.x 是官方「全新改版」的开发者预览版，从 NW.js 换成 Electron
（实测 2.02.2607271 = Electron 36.6.0 / Chromium 136），而 1.06.x 仍是 Stable，
因此必须双轨兼容，不能替换。

实测依据（2026-08-20，IDE 2.02.2607271 真机）：
- Contents/MacOS/wechatdevtools 与 Resources/package.nw 均已不存在
  → 入口改为 Contents/MacOS/Electron（Info.plist 的 CFBundleExecutable）
- 进程命令行不含 "wechatdevtools" 子串，旧 pkill 模式一个都杀不到
- --project= 不再被识别（CDP target 显示 projectpath 为空），
  正确姿势是先带 --remote-debugging-port 起进程，再用 cli open --project
- 6 秒 CDP 采集单条响应 634 KiB，超过 asyncio 默认 64 KiB 上限近 10 倍
"""
import asyncio
import plistlib
import sys

import pytest

from wechat_devtools_mcp.core import node_bridge
from wechat_devtools_mcp.tools import ide


class TestDaemonStreamLimit:
    """L1：daemon 响应可能远超 asyncio 默认 64 KiB 上限。"""

    def test_stream_limit_is_raised_well_above_default(self):
        """必须显式抬高 limit，否则大响应会让 readline 抛 LimitOverrunError。"""
        assert hasattr(node_bridge, "_STREAM_LIMIT"), "需要定义 _STREAM_LIMIT"
        assert node_bridge._STREAM_LIMIT >= 8 * 1024 * 1024, (
            "实测 6 秒 CDP 采集就有 634 KiB，长采集需要更大余量"
        )

    @pytest.mark.asyncio
    async def test_daemon_spawned_with_limit(self, monkeypatch, tmp_path):
        """_ensure_daemon 必须把 limit 传给 create_subprocess_exec。"""
        captured = {}

        class _FakeProc:
            returncode = None
            stdin = None

            def __init__(self):
                self.stdout = asyncio.StreamReader()
                self.stdout.feed_data(b'{"ready":true}\n')

            def kill(self):
                pass

        async def fake_exec(*args, **kwargs):
            captured.update(kwargs)
            return _FakeProc()

        bundle = tmp_path / "dist"
        bundle.mkdir()
        (bundle / "daemon.bundle.js").write_text("//", encoding="utf-8")

        monkeypatch.setattr(node_bridge, "_SCRIPTS_DIR", str(tmp_path))
        monkeypatch.setattr(node_bridge, "_daemon_process", None)
        monkeypatch.setattr(node_bridge, "_reader_task", None)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        monkeypatch.setattr(
            node_bridge, "_response_reader", lambda: asyncio.sleep(0)
        )

        await node_bridge._ensure_daemon()
        node_bridge._kill_daemon()

        assert "limit" in captured, "create_subprocess_exec 未传 limit"
        assert captured["limit"] >= 8 * 1024 * 1024


class TestMacosRuntimeDetection:
    """L1/L2：macOS 下 NW.js(1.x) 与 Electron(2.x) 双轨识别。"""

    def _fake_plist(self, monkeypatch, executable):
        def fake_load(fp):
            return {"CFBundleExecutable": executable}
        monkeypatch.setattr(plistlib, "load", fake_load)
        monkeypatch.setattr("builtins.open", lambda *a, **kw: _NullFile())

    def test_electron_layout_detected(self, monkeypatch):
        """2.x：无 package.nw，入口取 CFBundleExecutable。"""
        monkeypatch.setattr(
            ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli"
        )
        monkeypatch.setattr(sys, "platform", "darwin")

        exists = {
            "/Applications/wechatwebdevtools.app/Contents/MacOS/Electron": True,
            "/Applications/wechatwebdevtools.app/Contents/Info.plist": True,
        }
        monkeypatch.setattr(ide.os.path, "exists", lambda p: exists.get(p, False))
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "Electron")

        cmd, kill, runtime = ide._resolve_ide_executable_for_cdp()
        assert runtime == "electron"
        assert cmd == ["/Applications/wechatwebdevtools.app/Contents/MacOS/Electron"]
        # Electron 不接受 package.nw 入口参数
        assert len(cmd) == 1
        # kill 模式必须能匹配到 .../wechatwebdevtools.app/Contents/MacOS/Electron
        assert "wechatwebdevtools.app" in kill

    def test_nwjs_layout_still_supported(self, monkeypatch):
        """1.x：package.nw 存在时仍走 NW.js 老路径。"""
        monkeypatch.setattr(
            ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli"
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide.os.path, "exists", lambda p: True)
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "wechatdevtools")

        cmd, kill, runtime = ide._resolve_ide_executable_for_cdp()
        assert runtime == "nwjs"
        assert cmd == [
            "/Applications/wechatwebdevtools.app/Contents/MacOS/wechatdevtools",
            "/Applications/wechatwebdevtools.app/Contents/Resources/package.nw",
        ]
        assert "wechatwebdevtools.app" in kill

    def test_kill_pattern_matches_both_runtimes(self, monkeypatch):
        """kill 模式按 .app 包路径匹配，对 1.x 与 2.x 同时成立。"""
        monkeypatch.setattr(
            ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli"
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide.os.path, "exists", lambda p: True)
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "wechatdevtools")
        _, kill, _ = ide._resolve_ide_executable_for_cdp()

        nwjs_cmdline = "/Applications/wechatwebdevtools.app/Contents/MacOS/wechatdevtools"
        electron_cmdline = "/Applications/wechatwebdevtools.app/Contents/MacOS/Electron"
        assert kill in nwjs_cmdline
        assert kill in electron_cmdline
        # 旧模式对 Electron 无效，正是本次故障根因
        assert "wechatdevtools" not in electron_cmdline

    def test_missing_executable_raises(self, monkeypatch):
        monkeypatch.setattr(
            ide, "CLI_PATH", "/Applications/wechatwebdevtools.app/Contents/MacOS/cli"
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide.os.path, "exists", lambda p: False)
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "Electron")
        with pytest.raises(FileNotFoundError, match="IDE 主程序"):
            ide._resolve_ide_executable_for_cdp()


class TestCdpSourceParsing:
    """L3：2.x 的 target URL 结构变化，来源解析要跟上。

    实测 2.x：
      渲染层 http://127.0.0.1:57905/__pageframe__/pages/home/index
      逻辑层 http://127.0.0.1:57905/appservice/s0/_sessionId/simulator-app-session-s0/mainframe
    1.x 逻辑层则是 http://127.0.0.1:<port>/appservice/mainframe
    """

    def _classify(self, url, text="boom"):
        from wechat_devtools_mcp.utils.cdp_helpers import _classify_cdp_log
        return _classify_cdp_log({
            "type": "RUNTIME_CONSOLE", "url": url,
            "content": {"type": "error", "args": [text]},
        })

    def test_pageframe_source_is_page_path(self):
        _, _, source = self._classify(
            "http://127.0.0.1:57905/__pageframe__/pages/home/index"
        )
        assert source == "pages/home/index", "渲染层来源应还原为页面路径"

    def test_appservice_v2_source_normalized(self):
        _, _, source = self._classify(
            "http://127.0.0.1:57905/appservice/s0/_sessionId/simulator-app-session-s0/mainframe?load=1"
        )
        assert source == "appservice", "2.x 逻辑层路径含 session 段，应归一化"

    def test_appservice_v1_source_normalized(self):
        _, _, source = self._classify("http://127.0.0.1:8080/appservice/mainframe")
        assert source == "appservice", "1.x 逻辑层也归一化到同一标识"

    def test_electron_shell_logs_filtered_as_system_noise(self):
        """IDE 2.x 外壳页日志属系统噪音，不应计入业务日志。"""
        from wechat_devtools_mcp.utils.cdp_helpers import _format_cdp_logs_v2
        raw = [
            {
                "type": "RUNTIME_CONSOLE",
                "url": "file:///Applications/wechatwebdevtools.app/Contents/Resources/app.asar/html/electron-entrance.html",
                "content": {"type": "error", "args": ["ide shell noise"]},
            },
            {
                "type": "RUNTIME_CONSOLE",
                "url": "http://127.0.0.1:57905/__pageframe__/pages/home/index",
                "content": {"type": "error", "args": ["real app error"]},
            },
        ]
        out = _format_cdp_logs_v2(raw, "concise", 50)
        msgs = [l["message"] for l in out["logs"]]
        assert "real app error" in msgs
        assert "ide shell noise" not in msgs
        assert out["summary"]["errors"] == 1


class TestIdeStateFiles:
    """L4：IDE 自己写的状态文件比猜端口可靠。

    实测路径（macOS，IDE 2.02）：
      ~/Library/Application Support/微信开发者工具/<32位hash>/Default/
        .ide        → 11071   IDE 服务端口，随每次启动刷新
        .cli        → 3799    CLI 端口
        .ide-status → On      服务端口开关状态
    """

    def _make_profile(self, tmp_path, name, ide_port, status="On", cli_port="3799"):
        d = tmp_path / name / "Default"
        d.mkdir(parents=True)
        (d / ".ide").write_text(str(ide_port), encoding="utf-8")
        (d / ".cli").write_text(cli_port, encoding="utf-8")
        (d / ".ide-status").write_text(status, encoding="utf-8")
        return d

    def test_reads_ide_port(self, tmp_path, monkeypatch):
        from wechat_devtools_mcp.core import ide_state
        self._make_profile(tmp_path, "a" * 32, 11071)
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        assert ide_state.read_ide_port() == 11071

    def test_reads_service_port_status(self, tmp_path, monkeypatch):
        from wechat_devtools_mcp.core import ide_state
        self._make_profile(tmp_path, "b" * 32, 11071, status="On")
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        assert ide_state.read_service_port_enabled() is True

    def test_service_port_off_detected(self, tmp_path, monkeypatch):
        """服务端口关闭是 CLI_TIMEOUT 的头号原因，必须能主动识别。"""
        from wechat_devtools_mcp.core import ide_state
        self._make_profile(tmp_path, "c" * 32, 11071, status="Off")
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        assert ide_state.read_service_port_enabled() is False

    def test_newest_profile_wins(self, tmp_path, monkeypatch):
        """多 profile 共存（不同版本/渠道）时取最近写入的那个。"""
        import os
        import time
        from wechat_devtools_mcp.core import ide_state
        old = self._make_profile(tmp_path, "d" * 32, 27522)
        new = self._make_profile(tmp_path, "e" * 32, 11071)
        past = time.time() - 86400
        os.utime(old / ".ide", (past, past))
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        assert ide_state.read_ide_port() == 11071

    def test_missing_state_returns_none(self, tmp_path, monkeypatch):
        from wechat_devtools_mcp.core import ide_state
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        assert ide_state.read_ide_port() is None
        assert ide_state.read_service_port_enabled() is None

    def test_windows_2x_nested_user_data_layout(self, tmp_path, monkeypatch):
        """Windows 2.x 实测（2026-09-04，2.02.2608060）：状态文件在
        <base>\\微信开发者工具\\User Data\\<hash>\\Default\\ 下，比 1.x 多一层 User Data。"""
        import sys
        from wechat_devtools_mcp.core import ide_state
        profile = tmp_path / "微信开发者工具" / "User Data" / "8bd760e6" / "Default"
        profile.mkdir(parents=True)
        (profile / ".ide").write_text("14320", encoding="utf-8")
        (profile / ".ide-status").write_text("On", encoding="utf-8")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
        assert ide_state.read_ide_port() == 14320
        assert ide_state.read_service_port_enabled() is True

    def test_detect_ide_port_prefers_state_file(self, tmp_path, monkeypatch):
        """build._detect_ide_port 应优先采信 .ide，而不是硬编码候选列表。"""
        from wechat_devtools_mcp.core import ide_state
        from wechat_devtools_mcp.tools import build
        self._make_profile(tmp_path, "f" * 32, 45678)
        monkeypatch.setattr(ide_state, "_user_data_dirs", lambda: [str(tmp_path)])
        monkeypatch.setattr(build, "_port_open", lambda p: p == 45678)
        assert build._detect_ide_port() == 45678


class TestIdeReadyGate:
    """L2 竞态防护：CLI open 之前必须确认 CDP 与 IDE 服务都已监听。

    实测踩过：只固定 sleep 8s 就调 cli open，IDE 服务尚未起来，CLI 于是另起一个
    不带 CDP 的实例，我们那个被单实例锁挤掉 —— 结果 project_opened=true
    但 CDP 端口连接被拒。
    """

    @pytest.mark.asyncio
    async def test_waits_until_both_ports_listen(self, monkeypatch):
        seq = {"n": 0}

        def fake_listen(port):
            # 前两轮都没起来，第三轮才就绪
            seq["n"] += 1
            return seq["n"] > 4

        monkeypatch.setattr(ide, "_port_listening", fake_listen)
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 11071)
        cdp_ready, service_ready = await ide._wait_ide_ready(9223, timeout=15)
        assert cdp_ready and service_ready

    @pytest.mark.asyncio
    async def test_reports_cdp_not_ready(self, monkeypatch):
        monkeypatch.setattr(ide, "_port_listening", lambda p: False)
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 11071)
        cdp_ready, service_ready = await ide._wait_ide_ready(9223, timeout=2)
        assert cdp_ready is False
        assert service_ready is False


class TestBuildCdpPort:
    """compile 的 WXML 错误捕获也要能跟着 cdp_port 走。

    9222 常被 Chrome 占用（实测本机就是），写死端口会让 wxml_errors 静默恒空。
    """

    @pytest.mark.asyncio
    async def test_compile_forwards_cdp_port(self, monkeypatch, tmp_path):
        import json
        from unittest.mock import AsyncMock, patch

        from wechat_devtools_mcp.models.schemas import WechatBuildInput
        from wechat_devtools_mcp.tools.build import wechat_build

        calls = []

        async def fake_node(script, *args, **kw):
            calls.append((script, args))
            return {"success": True, "data": []}

        async def fake_cli(*args, **kw):
            return {"success": True, "stdout": "", "stderr": "", "return_code": 0,
                    "command": "cli"}

        with patch("wechat_devtools_mcp.tools.build._run_cli",
                   new_callable=AsyncMock, side_effect=fake_cli), \
             patch("wechat_devtools_mcp.tools.build._run_node_script",
                   new_callable=AsyncMock, side_effect=fake_node), \
             patch("wechat_devtools_mcp.tools.build._detect_ide_port", lambda: None), \
             patch("wechat_devtools_mcp.tools.build._check_npm_stale", lambda p: None):
            params = WechatBuildInput(action="compile", project_path=str(tmp_path),
                                      cdp_port=9333)
            json.loads(await wechat_build(params))

        cdp_calls = [a for s, a in calls if s == "cdp_listener.js"]
        assert cdp_calls, "compile 未做 CDP 采集"
        assert "9333" in cdp_calls[0], f"cdp_port 未透传，实际参数：{cdp_calls[0]}"


class _NullFile:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b""
