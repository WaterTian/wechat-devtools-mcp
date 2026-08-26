"""#22 compile 假成功检测：CLI returncode=0 但 stderr 含致命 pattern 时降级为 fail。"""
import json
from unittest.mock import patch, AsyncMock
import pytest

from wechat_devtools_mcp.tools.build import (
    wechat_build,
    _detect_fatal_errors,
    _FATAL_COMPILE_PATTERNS,
)
from wechat_devtools_mcp.models.schemas import WechatBuildInput


class TestDetectFatalErrors:
    """_detect_fatal_errors 筛选逻辑。"""

    def test_detects_eacces(self):
        errors = ["× #initialize-error: Error: listen EACCES: permission denied 127.0.0.1:3799"]
        assert _detect_fatal_errors(errors) == errors

    def test_detects_eaddrinuse(self):
        errors = ["listen EADDRINUSE: address already in use :::9420"]
        assert len(_detect_fatal_errors(errors)) == 1

    def test_detects_initialize_error(self):
        errors = ["× #initialize-error: compile service crashed"]
        assert len(_detect_fatal_errors(errors)) == 1

    def test_ignores_business_error(self):
        """业务错误（普通 error 关键词）不应命中。"""
        errors = [
            "[error] app.json: pages[3] 不存在",
            "warning: 0 errors were suppressed",
        ]
        assert _detect_fatal_errors(errors) == []

    def test_all_patterns_nonempty(self):
        """致命 pattern 列表非空，防止误改为空元组。"""
        assert len(_FATAL_COMPILE_PATTERNS) > 0


class TestCompileFatalDetection:
    """compile action 对致命错误的降级行为。"""

    @pytest.mark.asyncio
    async def test_eacces_returncode_zero_is_downgraded_to_fail(self, set_env_vars):
        """CLI returncode=0 但 stderr 含 EACCES，应返回 success:false 而非 success:true。"""
        fake_cli = {
            "success": True,  # CLI 进程本身返回 0
            "stdout": "",
            "stderr": "× #initialize-error: Error: listen EACCES: permission denied 127.0.0.1:3799\n",
        }
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli):
            params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
            result = json.loads(await wechat_build(params))

            assert result["success"] is False
            assert "fatal_errors" in result
            assert len(result["fatal_errors"]) >= 1
            assert "EACCES" in result["fatal_errors"][0]

    @pytest.mark.asyncio
    async def test_benign_error_keyword_does_not_downgrade(self, set_env_vars):
        """普通 error 关键词（非致命 pattern）不应触发降级。"""
        fake_cli = {"success": True, "stdout": "", "stderr": "[info] 0 errors, 0 warnings\n"}
        with patch("wechat_devtools_mcp.tools.build._run_cli", return_value=fake_cli), \
             patch("wechat_devtools_mcp.tools.build.socket") as mock_socket, \
             patch("wechat_devtools_mcp.tools.build.invalidate_connection", new_callable=AsyncMock, return_value=True), \
             patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value={"success": True}), \
             patch("wechat_devtools_mcp.tools.build.asyncio.sleep", new_callable=AsyncMock):
            # 端口不可达，跳过重连逻辑以简化断言
            mock_socket.create_connection.side_effect = ConnectionRefusedError
            params = WechatBuildInput(action="compile", project_path=str(set_env_vars))
            result = json.loads(await wechat_build(params))

            assert result["success"] is True
            assert "fatal_errors" not in result.get("data", {})
