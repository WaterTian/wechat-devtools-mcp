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
        """两个探测点都不存在（路径根本不在本机）→ 保持旧行为，不抛错。"""
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(
            ide, "CLI_PATH",
            r"C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat",
        )

        cmd_prefix, kill_pattern, runtime = ide._resolve_ide_executable_for_cdp()

        assert runtime == "win32"
        assert cmd_prefix == [
            r"C:\Program Files (x86)\Tencent\微信web开发者工具\微信开发者工具.exe"
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

        async def fake_wait_ready(port, timeout=60):
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

        async def _ok_ready(port, timeout=60):
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
