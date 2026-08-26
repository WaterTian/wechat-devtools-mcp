"""IDE cdp_enabled 启动命令跨平台推导测试。

覆盖 _resolve_ide_executable_for_cdp 和 _kill_existing_ide。
基于 mac mini 真机实证（2026-04-29，IDE 1.x / NW.js）：
- macOS 主程序是 wechatdevtools，必须传 package.nw 入口
- cli quit 不识别 spawn 实例，必须 pkill -f 清理

2026-08-20 更新（IDE 2.x / Electron 实证）：
- 返回值扩展为三元组，新增 runtime 用于区分 nwjs / electron / win32
- kill 模式改用 .app 包路径，同时覆盖两代（旧的 "wechatdevtools" 匹配不到 Electron）
- 2.x 专项断言见 test_devtools_v2_adaptation.py
"""
import sys
import pytest
from unittest.mock import patch

from wechat_devtools_mcp.tools import ide


class TestResolveIdeExecutableForCdp:
    """_resolve_ide_executable_for_cdp 跨平台路径推导。"""

    def test_windows_returns_exe_replacement(self, monkeypatch):
        monkeypatch.setattr(
            ide, "CLI_PATH",
            r"C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat",
        )
        monkeypatch.setattr(sys, "platform", "win32")
        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()
        assert cmd_prefix == [
            r"C:\Program Files (x86)\Tencent\微信web开发者工具\微信开发者工具.exe"
        ]
        assert kill_pattern == "wechatdevtools.exe"
        assert runtime == "win32"

    def test_macos_returns_wechatdevtools_with_package_nw(self, monkeypatch):
        monkeypatch.setattr(
            ide, "CLI_PATH",
            "/Applications/wechatwebdevtools.app/Contents/MacOS/cli",
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        # 模拟 IDE 主程序和 package.nw 都存在
        monkeypatch.setattr(ide.os.path, "exists", lambda p: True)
        # 1.x 的 Info.plist 声明的入口就是 wechatdevtools
        # （不打桩会读到本机真实的 2.x plist，那是 Electron）
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "wechatdevtools")

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()
        assert cmd_prefix == [
            "/Applications/wechatwebdevtools.app/Contents/MacOS/wechatdevtools",
            "/Applications/wechatwebdevtools.app/Contents/Resources/package.nw",
        ]
        assert runtime == "nwjs"
        # kill 模式改为 .app 包路径，仍能匹配到 NW.js 主程序命令行
        assert kill_pattern == "/Applications/wechatwebdevtools.app"
        assert kill_pattern in cmd_prefix[0]

    def test_macos_missing_executable_raises(self, monkeypatch):
        monkeypatch.setattr(
            ide, "CLI_PATH",
            "/Applications/wechatwebdevtools.app/Contents/MacOS/cli",
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide.os.path, "exists", lambda p: False)

        with pytest.raises(FileNotFoundError, match="IDE 主程序"):
            ide._resolve_ide_executable_for_cdp()

    def test_macos_without_package_nw_falls_to_electron(self, monkeypatch):
        """无 package.nw 不再报错，而是判定为 IDE 2.x(Electron)。

        行为变更（2026-08-20）：2.x 移除了 package.nw，旧实现在此直接抛
        FileNotFoundError，导致 macOS 上默认参数的 open 完全不可用。
        """
        monkeypatch.setattr(
            ide, "CLI_PATH",
            "/Applications/wechatwebdevtools.app/Contents/MacOS/cli",
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        electron = "/Applications/wechatwebdevtools.app/Contents/MacOS/Electron"
        monkeypatch.setattr(ide.os.path, "exists", lambda p: p == electron)
        monkeypatch.setattr(ide, "_read_bundle_executable", lambda c: "Electron")

        cmd_prefix, _, runtime = ide._resolve_ide_executable_for_cdp()
        assert runtime == "electron"
        assert cmd_prefix == [electron]

    def test_unsupported_platform_raises(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        with pytest.raises(NotImplementedError, match="linux"):
            ide._resolve_ide_executable_for_cdp()


@pytest.mark.asyncio
class TestKillExistingIde:
    """_kill_existing_ide 平台分发测试。"""

    async def test_windows_uses_taskkill(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        called = {}

        def fake_run(args, **kwargs):
            called["args"] = args

        with patch("subprocess.run", side_effect=fake_run):
            await ide._kill_existing_ide("wechatdevtools.exe")

        assert called["args"][0] == "taskkill"
        assert "wechatdevtools.exe" in called["args"]

    async def test_macos_uses_pkill(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        called = {}

        def fake_run(args, **kwargs):
            called["args"] = args

        with patch("subprocess.run", side_effect=fake_run):
            await ide._kill_existing_ide("wechatdevtools")

        assert called["args"][0] == "pkill"
        assert "wechatdevtools" in called["args"]
        assert "-f" in called["args"]


class TestCdpLaunchProjectArgFormat:
    """cdp_enabled 启动命令的 --project 参数格式（实证：Mac 用等号，Windows 不带）。"""

    def test_macos_project_uses_equals_form(self, monkeypatch):
        """macOS NW.js 主程序透传 --project=path 形式（实测）。"""
        monkeypatch.setattr(
            ide, "CLI_PATH",
            "/Applications/wechatwebdevtools.app/Contents/MacOS/cli",
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(ide.os.path, "exists", lambda p: True)

        cmd_prefix, _, _ = ide._resolve_ide_executable_for_cdp()
        cmd_args = list(cmd_prefix) + ["--remote-debugging-port=9222"]
        cmd_args.append("--project=/Users/test/proj")

        assert "--project=/Users/test/proj" in cmd_args
        # 不应出现拆开的 ["--project", path] 形式
        assert "--project" not in cmd_args or any(
            a.startswith("--project=") for a in cmd_args
        )
