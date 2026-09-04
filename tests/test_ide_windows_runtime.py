"""Windows 侧 IDE 1.x(NW.js) / 2.x(Electron) 双轨判定测试。

背景（2026-09-03）：开发者工具 2.x 已于 2026-08-18 转为官方 Stable（2.02.2608040），
1.06 已从下载页下架。Windows 用户升级后的目录布局不再是 NW.js 的
``<root>\\code\\package.nw``，旧实现把 ``cli.bat`` 字符串替换成 ``微信开发者工具.exe``、
runtime 硬编码 ``"win32"``，会让 cdp_enabled 模式的 open 走错分支。

判定依据照抄官方 wechatide-skill 的 ``skills/installer/scripts/install-root.mjs``
（IDE 2.02.2607271 与 2.02.2608060 自带，内容一致）：

    win32:  nw       = <root>\\code\\package.nw\\package.json
            electron = <root>\\resources\\app.asar.unpacked\\package.json

Electron 主程序文件名官方脚本给了三个候选（App Paths 注册表键名）：
``wechatdevtools.exe`` / ``wechatwebdevtools.exe`` / ``微信开发者工具.exe``，
真机未验证，按存在性择一；都不存在则退回旧的字符串替换行为。
"""
import os
import sys

import pytest

from wechat_devtools_mcp.tools import ide


def _make_root(tmp_path, layout: str, exe_names=("微信开发者工具.exe",)) -> str:
    root = tmp_path / "微信web开发者工具"
    root.mkdir()
    (root / "cli.bat").write_text("@echo off", encoding="utf-8")
    if layout == "electron":
        pkg = root / "resources" / "app.asar.unpacked"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"version":"2.02.2608060"}', encoding="utf-8")
    elif layout == "nwjs":
        pkg = root / "code" / "package.nw"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"version":"1.06.2504060"}', encoding="utf-8")
    for name in exe_names:
        (root / name).write_bytes(b"MZ")
    return str(root)


class TestWindowsRuntimeDetection:

    def test_electron_layout_detected(self, monkeypatch, tmp_path):
        root = _make_root(tmp_path, "electron")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()

        assert runtime == "electron"
        assert cmd_prefix == [os.path.join(root, "微信开发者工具.exe")]
        # taskkill 用镜像名，且必须是实际选中的那个主程序
        assert kill_pattern == "微信开发者工具.exe"

    def test_electron_exe_candidates_fallback_order(self, monkeypatch, tmp_path):
        """首选名不存在时，按官方候选顺序找下一个。"""
        root = _make_root(tmp_path, "electron", exe_names=("wechatwebdevtools.exe",))
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()

        assert runtime == "electron"
        assert cmd_prefix == [os.path.join(root, "wechatwebdevtools.exe")]
        assert kill_pattern == "wechatwebdevtools.exe"

    def test_electron_layout_without_exe_raises(self, monkeypatch, tmp_path):
        root = _make_root(tmp_path, "electron", exe_names=())
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        with pytest.raises(FileNotFoundError, match="IDE 主程序"):
            ide._resolve_ide_executable_for_cdp()

    def test_nwjs_layout_keeps_legacy_behaviour(self, monkeypatch, tmp_path):
        """1.x 布局：主程序仍是 微信开发者工具.exe，kill 仍用 wechatdevtools.exe。"""
        root = _make_root(tmp_path, "nwjs")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()

        assert runtime == "nwjs"
        assert cmd_prefix == [os.path.join(root, "微信开发者工具.exe")]
        assert kill_pattern == "wechatdevtools.exe"

    def test_unknown_layout_falls_back_to_string_replacement(self, monkeypatch):
        """两个探测点都不存在（路径根本不在本机）→ 保持旧行为，不抛错。

        必须用绝不存在的根目录：装了 IDE 的 Windows 机上默认安装目录真实存在，会判成 electron。
        """
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(
            ide, "CLI_PATH",
            r"C:\__nonexistent_wechat_devtools_test__\微信web开发者工具\cli.bat",
        )

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()

        assert runtime == "win32"
        assert cmd_prefix == [
            r"C:\__nonexistent_wechat_devtools_test__\微信web开发者工具\微信开发者工具.exe"
        ]
        assert kill_pattern == "wechatdevtools.exe"


class TestWindowsElectronOpenIsTwoStep:
    """Windows 2.x 也必须走「先带 CDP 起进程，再 cli open」的两步式。"""

    @pytest.mark.asyncio
    async def test_open_does_not_pass_project_to_exe(self, monkeypatch, tmp_path):
        import asyncio
        import subprocess

        root = _make_root(tmp_path, "electron")
        exe = os.path.join(root, "微信开发者工具.exe")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        popen_calls = []

        class _FakeProc:
            returncode = None

            def poll(self):
                return None

        def fake_popen(args, **kwargs):
            popen_calls.append(list(args))
            return _FakeProc()

        cli_calls = []

        async def fake_run_cli(*args, **kwargs):
            cli_calls.append(args)
            return {"success": True, "stdout": "", "stderr": ""}

        async def fake_wait_ready(port, timeout=60, **kw):
            return True, True

        async def fake_kill(pattern):
            pass

        async def fake_node(*args, **kwargs):
            return {"success": True, "data": []}

        async def fake_sleep(_):
            return None

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        monkeypatch.setattr(ide, "_run_cli", fake_run_cli)
        monkeypatch.setattr(ide, "_wait_ide_ready", fake_wait_ready)
        monkeypatch.setattr(ide, "_kill_existing_ide", fake_kill)
        monkeypatch.setattr(ide, "_run_node_script", fake_node)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        params = WechatIdeInput(action="open", project_path=r"D:\proj", cdp_port=9223)
        import json
        result = json.loads(await ide._action_open(params))

        assert result["success"] is True, result
        assert popen_calls and popen_calls[0][0] == exe
        assert "--remote-debugging-port=9223" in popen_calls[0]
        # Electron 不识别 --project，不能塞给主程序（任何形式都不行）
        assert not any(a.startswith("--project") or "D:\\proj" in a for a in popen_calls[0]), popen_calls[0]
        assert cli_calls and cli_calls[0][:3] == ("open", "--project", r"D:\proj")
        assert result["data"]["ide_runtime"] == "electron"
        assert result["data"]["project_opened"] is True


class TestWindowsElectronOpenServiceReadyRelaxed:
    """Windows 2.x 真机实测（2026-09-04）：.ide 记录的服务端口在实例重启后不更新
    （stale），_wait_ide_ready 的 service 判据必然失败。此时不应阻塞 open ——
    CLI 自带服务发现（能找到真实端口），以 _run_cli 的实际结果为准。
    """

    @pytest.mark.asyncio
    async def test_open_proceeds_when_service_ready_false(self, monkeypatch, tmp_path):
        import asyncio
        import subprocess

        root = _make_root(tmp_path, "electron")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))

        class _FakeProc:
            returncode = None

            def poll(self):
                return None

        cli_calls = []

        async def fake_run_cli(*args, **kwargs):
            cli_calls.append(args)
            return {"success": True, "stdout": "", "stderr": ""}

        async def _cdp_ok_service_no(port, timeout=60, **kw):
            return True, False  # Windows 2.x 真机现象：CDP 就绪但 .ide stale

        async def _noop(*a, **k):
            return None

        async def fake_node(*a, **k):
            return {"success": True, "data": []}

        monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: _FakeProc())
        monkeypatch.setattr(ide, "_run_cli", fake_run_cli)
        monkeypatch.setattr(ide, "_wait_ide_ready", _cdp_ok_service_no)
        monkeypatch.setattr(ide, "_kill_existing_ide", _noop)
        monkeypatch.setattr(ide, "_run_node_script", fake_node)
        monkeypatch.setattr(asyncio, "sleep", _noop)

        import json
        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        result = json.loads(await ide._action_open(
            WechatIdeInput(action="open", cdp_port=9223, project_path=r"D:\proj")))

        assert result["success"] is True, result
        assert cli_calls and cli_calls[0][:3] == ("open", "--project", r"D:\proj")
        assert result["data"]["project_opened"] is True

    @pytest.mark.asyncio
    async def test_service_not_ready_still_fails_on_macos_electron(self, monkeypatch, tmp_path):
        """macOS 保持原语义：service 判据不过时继续阻塞（CLI 会另起不带 CDP 的实例）。"""
        import asyncio
        import subprocess

        # 构造 darwin 布局：cli 在 Contents/MacOS 下，无 package.nw → electron
        app = tmp_path / "wechatwebdevtools.app"
        macos = app / "Contents" / "MacOS"
        macos.mkdir(parents=True)
        (macos / "Electron").write_bytes(b"MZ")
        cli = macos / "cli"
        monkeypatch.setattr(sys, "platform", "darwin")
        # darwin 分支用 "/" 做字符串分割，Windows 上跑测试要显式正斜杠
        monkeypatch.setattr(ide, "CLI_PATH", str(cli).replace("\\", "/"))

        class _FakeProc:
            returncode = None

            def poll(self):
                return None

        async def _cdp_ok_service_no(port, timeout=60, **kw):
            return True, False

        async def _noop(*a, **k):
            return None

        monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: _FakeProc())
        monkeypatch.setattr(ide, "_wait_ide_ready", _cdp_ok_service_no)
        monkeypatch.setattr(ide, "_kill_existing_ide", _noop)
        monkeypatch.setattr(asyncio, "sleep", _noop)

        import json
        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        result = json.loads(await ide._action_open(
            WechatIdeInput(action="open", cdp_port=9223, project_path="/tmp/proj")))

        assert result["success"] is False
        assert "服务端口" in result.get("message", "")


class TestOpenFallsBackToDefaultProjectPath:
    """`open` 未显式传 project_path 时必须回退到 WECHAT_PROJECT_PATH。

    真机发现（2026-09-03，IDE 2.02.2608060）：不传 project_path 时 2.x 两步式的第二步
    （cli open --project）被整个跳过，返回 project_opened: null，项目其实是 IDE 自己的
    会话恢复顺手打开的——换台机器或清过会话就打不开。文档一直声称「不填则使用
    WECHAT_PROJECT_PATH」，代码却只看 params.project_path。
    """

    @pytest.mark.asyncio
    async def test_electron_open_uses_default_project_path(self, monkeypatch, tmp_path):
        import asyncio
        import subprocess

        root = _make_root(tmp_path, "electron")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))
        monkeypatch.setattr(ide, "DEFAULT_PROJECT_PATH", r"D:\default-proj")

        class _FakeProc:
            returncode = None

            def poll(self):
                return None

        cli_calls = []

        async def fake_run_cli(*args, **kwargs):
            cli_calls.append(args)
            return {"success": True, "stdout": "", "stderr": ""}

        async def _ok_ready(port, timeout=60, **kw):
            return True, True

        async def _noop(*a, **k):
            return None

        async def fake_node(*a, **k):
            return {"success": True, "data": []}

        monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: _FakeProc())
        monkeypatch.setattr(ide, "_run_cli", fake_run_cli)
        monkeypatch.setattr(ide, "_wait_ide_ready", _ok_ready)
        monkeypatch.setattr(ide, "_kill_existing_ide", _noop)
        monkeypatch.setattr(ide, "_run_node_script", fake_node)
        monkeypatch.setattr(asyncio, "sleep", _noop)

        import json
        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        result = json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9223)))

        assert result["success"] is True, result
        assert cli_calls and cli_calls[0][:3] == ("open", "--project", r"D:\default-proj")
        assert result["data"]["project_opened"] is True


class TestWindowsElectronReadyWithoutStalePort:
    """Windows 2.x 的 .ide 端口 stale（0c492ec 真机发现）：不能拿它当就绪判据，否则每次 open 白等 60s。

    改用「CDP 已监听 + /json/list 出现 IDE 外壳 target」，等到即返回。
    """

    @pytest.mark.asyncio
    async def test_wait_ide_ready_returns_fast_via_shell_target(self, monkeypatch):
        import http.server
        import json as _json
        import threading

        class _H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = _json.dumps([{"type": "page", "url": "file:///.../electron-entrance.html"}]).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            monkeypatch.setattr(ide, "_port_listening", lambda p: True)
            # .ide 记录的是 stale 端口：read_ide_port 给一个根本没人监听的值也不该被用到
            monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 1)
            import time
            t0 = time.time()
            cdp_ready, service_ready = await ide._wait_ide_ready(srv.server_port, timeout=30, require_service=False)
            assert (cdp_ready, service_ready) == (True, True)
            assert time.time() - t0 < 5, "不应等到超时"
        finally:
            srv.shutdown()

    @pytest.mark.asyncio
    async def test_wait_ide_ready_default_still_requires_service_port(self, monkeypatch):
        """默认（macOS / 1.x）行为不变：服务端口不监听就一直等到超时。"""
        monkeypatch.setattr(ide, "_port_listening", lambda p: p == 9223)
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 11071)
        cdp_ready, service_ready = await ide._wait_ide_ready(9223, timeout=1)
        assert (cdp_ready, service_ready) == (True, False)

    @pytest.mark.asyncio
    async def test_open_on_windows_electron_passes_require_service_false(self, monkeypatch, tmp_path):
        import asyncio
        import json as _json
        import subprocess

        root = _make_root(tmp_path, "electron")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(ide, "CLI_PATH", os.path.join(root, "cli.bat"))
        monkeypatch.setattr(ide, "DEFAULT_PROJECT_PATH", r"D:\proj")

        class _P:
            returncode = None
            def poll(self): return None

        seen = {}

        async def fake_wait(port, timeout=60, require_service=True):
            seen["require_service"] = require_service
            return True, True

        async def _noop(*a, **k): return None
        async def fake_cli(*a, **k): return {"success": True, "stdout": "", "stderr": ""}
        async def fake_node(*a, **k): return {"success": True, "data": []}
        async def fake_targets(*a, **k): return True

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _P())
        monkeypatch.setattr(ide, "_wait_ide_ready", fake_wait)
        monkeypatch.setattr(ide, "_kill_existing_ide", _noop)
        monkeypatch.setattr(ide, "_run_cli", fake_cli)
        monkeypatch.setattr(ide, "_run_node_script", fake_node)
        monkeypatch.setattr(ide, "_wait_miniprogram_targets", fake_targets)
        monkeypatch.setattr(asyncio, "sleep", _noop)

        from wechat_devtools_mcp.models.schemas import WechatIdeInput
        result = _json.loads(await ide._action_open(WechatIdeInput(action="open", cdp_port=9223)))
        assert result["success"] is True, result
        assert seen["require_service"] is False
