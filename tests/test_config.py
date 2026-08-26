"""配置加载和路径解析测试。"""
import os
import pytest
from wechat_devtools_mcp.core.cli import _resolve_project_path, _build_global_args


class TestResolveProjectPath:
    """项目路径解析测试。"""

    def test_explicit_path_wins(self, set_env_vars):
        """显式传入路径应优先于环境变量。"""
        result = _resolve_project_path("D:\\Custom\\Path")
        assert result == "D:\\Custom\\Path"

    def test_env_fallback(self, monkeypatch, tmp_path):
        """未传路径时应使用默认路径。"""
        from wechat_devtools_mcp.core import config, cli
        monkeypatch.setattr(config, "DEFAULT_PROJECT_PATH", str(tmp_path))
        monkeypatch.setattr(cli, "DEFAULT_PROJECT_PATH", str(tmp_path))
        result = _resolve_project_path(None)
        assert result == str(tmp_path)


class TestBuildGlobalArgs:
    """CLI 全局参数构建测试。"""

    def test_empty_input(self):
        assert _build_global_args() == []

    def test_project_path_only(self):
        result = _build_global_args(project_path="D:\\proj")
        assert result == ["--project", "D:\\proj"]
