"""#18 qr_output/info_output 路径 resolve + #22 qr_output mtime 新鲜度检测。"""
import json
import os
import tempfile
from unittest.mock import patch
import pytest

from wechat_devtools_mcp.tools.build import wechat_build, _safe_mtime
from wechat_devtools_mcp.models.schemas import WechatBuildInput


class TestSafeMtime:
    def test_returns_zero_for_nonexistent(self, tmp_path):
        assert _safe_mtime(str(tmp_path / "missing.png")) == 0.0

    def test_returns_zero_for_none(self):
        assert _safe_mtime(None) == 0.0

    def test_returns_mtime_for_existing(self, tmp_path):
        p = tmp_path / "exists.png"
        p.write_bytes(b"x")
        assert _safe_mtime(str(p)) > 0


class TestPreviewPathResolve:
    """#18：preview 相对路径应 resolve 为绝对路径再下发 CLI。"""

    @pytest.mark.asyncio
    async def test_qr_output_relative_path_resolved(self, set_env_vars):
        fake_cli = {"success": True, "stdout": "ok", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli) as mock_cli:
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output="screenshots/qr.png",
            )
            await wechat_build(params)

            call_args = list(mock_cli.call_args[0])
            assert "--qr-output" in call_args
            qr_arg = call_args[call_args.index("--qr-output") + 1]
            # 必须是绝对路径
            assert os.path.isabs(qr_arg)
            # 必须在 project_path 下
            assert str(set_env_vars) in qr_arg

    @pytest.mark.asyncio
    async def test_qr_output_absolute_path_untouched(self, set_env_vars, tmp_path):
        fake_cli = {"success": True, "stdout": "ok", "stderr": ""}
        abs_path = str(tmp_path / "external" / "qr.png")
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli) as mock_cli:
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output=abs_path,
            )
            await wechat_build(params)

            call_args = list(mock_cli.call_args[0])
            qr_arg = call_args[call_args.index("--qr-output") + 1]
            assert qr_arg == abs_path

    @pytest.mark.asyncio
    async def test_info_output_relative_path_resolved(self, set_env_vars):
        fake_cli = {"success": True, "stdout": "ok", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli) as mock_cli:
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                info_output="build/info.json",
            )
            await wechat_build(params)

            call_args = list(mock_cli.call_args[0])
            assert "--info-output" in call_args
            info_arg = call_args[call_args.index("--info-output") + 1]
            assert os.path.isabs(info_arg)

    @pytest.mark.asyncio
    async def test_parent_dir_created_for_resolved_path(self, set_env_vars):
        """resolve 后的父目录应自动创建，避免 CLI 因目录不存在报错。"""
        fake_cli = {"success": True, "stdout": "ok", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli):
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output="subdir/nested/qr.png",
            )
            await wechat_build(params)
            assert os.path.isdir(str(set_env_vars / "subdir" / "nested"))


class TestPreviewStaleDetection:
    """#22：preview 成功但 qr_output 未刷新时发 warning。"""

    @pytest.mark.asyncio
    async def test_stale_qr_emits_warning(self, set_env_vars):
        """文件存在但 mtime 未变化时应返回 qr_stale_warning。"""
        qr = set_env_vars / "qr.png"
        qr.write_bytes(b"old_content")

        fake_cli = {"success": True, "stdout": "ok", "stderr": ""}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli):
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output=str(qr),
            )
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "qr_stale_warning" in result["data"]

    @pytest.mark.asyncio
    async def test_fresh_qr_no_warning(self, set_env_vars):
        """CLI 执行后 mtime 更新，应无 warning。"""
        qr = set_env_vars / "qr.png"
        qr.write_bytes(b"old")

        async def touch_file(*args, **kwargs):
            # 模拟 CLI 刷新了文件
            import time
            time.sleep(0.01)
            qr.write_bytes(b"new")
            return {"success": True, "stdout": "ok", "stderr": ""}

        with patch("wechat_devtools_mcp.tools.build._run_cli", side_effect=touch_file):
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output=str(qr),
            )
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "qr_stale_warning" not in result["data"]

    @pytest.mark.asyncio
    async def test_no_preexisting_qr_no_warning(self, set_env_vars):
        """qr_output 文件之前不存在，首次生成不应触发 stale warning。"""
        qr = set_env_vars / "first_time_qr.png"

        async def create_file(*args, **kwargs):
            qr.write_bytes(b"new")
            return {"success": True, "stdout": "ok", "stderr": ""}

        with patch("wechat_devtools_mcp.tools.build._run_cli", side_effect=create_file):
            params = WechatBuildInput(
                action="preview",
                project_path=str(set_env_vars),
                qr_output=str(qr),
            )
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "qr_stale_warning" not in result["data"]
