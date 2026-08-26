"""#19 compile 前检测 miniprogram_npm 是否缺失/过期，输出 warning。"""
import json
import os
import time
from unittest.mock import patch, AsyncMock
import pytest

from wechat_devtools_mcp.tools.build import wechat_build, _check_npm_stale
from wechat_devtools_mcp.models.schemas import WechatBuildInput


def _make_project(tmp_path, has_config=True, mp_subdir=None):
    """构造一个最小小程序项目目录结构。"""
    proj = tmp_path
    if has_config:
        config = {"miniprogramRoot": mp_subdir} if mp_subdir else {}
        (proj / "project.config.json").write_text(json.dumps(config), encoding="utf-8")
    return proj


class TestCheckNpmStale:
    def test_no_node_modules_returns_none(self, tmp_path):
        _make_project(tmp_path)
        assert _check_npm_stale(str(tmp_path)) is None

    def test_node_modules_without_miniprogram_npm(self, tmp_path):
        _make_project(tmp_path)
        (tmp_path / "node_modules").mkdir()
        warning = _check_npm_stale(str(tmp_path))
        assert warning is not None
        assert "miniprogram_npm 缺失" in warning

    def test_miniprogram_npm_fresher_than_node_modules(self, tmp_path):
        _make_project(tmp_path)
        nm = tmp_path / "node_modules"
        mpnpm = tmp_path / "miniprogram_npm"
        nm.mkdir()
        time.sleep(0.02)
        mpnpm.mkdir()
        assert _check_npm_stale(str(tmp_path)) is None

    def test_node_modules_fresher_than_miniprogram_npm(self, tmp_path):
        _make_project(tmp_path)
        mpnpm = tmp_path / "miniprogram_npm"
        nm = tmp_path / "node_modules"
        mpnpm.mkdir()
        time.sleep(0.02)
        nm.mkdir()
        warning = _check_npm_stale(str(tmp_path))
        assert warning is not None
        assert "未重新构建" in warning

    def test_respects_miniprogram_root(self, tmp_path):
        """miniprogramRoot 指向子目录时应在子目录内查找。"""
        _make_project(tmp_path, mp_subdir="miniprogram")
        mp_dir = tmp_path / "miniprogram"
        mp_dir.mkdir()
        (mp_dir / "node_modules").mkdir()
        warning = _check_npm_stale(str(tmp_path))
        assert warning is not None
        assert "miniprogram_npm 缺失" in warning


class TestCompileEmitsNpmWarning:
    @pytest.mark.asyncio
    async def test_compile_includes_npm_warning_in_data(self, set_env_vars):
        (set_env_vars / "project.config.json").write_text("{}", encoding="utf-8")
        (set_env_vars / "node_modules").mkdir()

        fake_cli = {"success": True, "stdout": "", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli), \
             patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
             patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value={"success": True}), \
             patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
            mock_socket.create_connection.side_effect = ConnectionRefusedError
            params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "npm_warning" in result["data"]
            assert "miniprogram_npm 缺失" in result["data"]["npm_warning"]
            assert "npm_warning" in result["message"] or "npm" in result["message"]

    @pytest.mark.asyncio
    async def test_compile_no_warning_when_npm_ok(self, set_env_vars):
        (set_env_vars / "project.config.json").write_text("{}", encoding="utf-8")

        fake_cli = {"success": True, "stdout": "", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli), \
             patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
             patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value={"success": True}), \
             patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
            mock_socket.create_connection.side_effect = ConnectionRefusedError
            params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "npm_warning" not in result["data"]
