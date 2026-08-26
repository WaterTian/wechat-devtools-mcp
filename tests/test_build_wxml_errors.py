"""compile 后 CDP 采集 WXML 错误测试。"""
import json
from unittest.mock import patch, AsyncMock
import pytest

from wechat_devtools_mcp.tools.build import _action_compile
from wechat_devtools_mcp.models.schemas import WechatBuildInput


def _make_cli_success():
    """模拟 CLI 编译成功的返回值。"""
    return {
        "success": True,
        "stdout": "",
        "stderr": "✓ compile success\n",
    }


def _make_cdp_wxml_error():
    """模拟 CDP 返回包含 WXML 错误的日志。"""
    return {
        "success": True,
        "data": [
            {
                "type": "LOG_ENTRY",
                "url": "pages/index/index.wxml",
                "content": {
                    "level": "error",
                    "text": "./pages/index/index.wxml(line 5): Bad attr 'wx:forr'",
                    "url": "pages/index/index.wxml",
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_compile_captures_wxml_errors():
    """编译成功但存在 WXML 错误时，errors 中应包含 WXML 错误。"""
    params = WechatBuildInput(action="compile", project_path="D:\\TestProject")

    with patch("wechat_devtools_mcp.tools.build._run_cli", new_callable=AsyncMock, return_value=_make_cli_success()), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=_make_cdp_wxml_error()), \
         patch("wechat_devtools_mcp.tools.build._resolve_project_path", return_value="D:\\TestProject"), \
         patch("wechat_devtools_mcp.tools.build._detect_ide_port", return_value=None), \
         patch("wechat_devtools_mcp.tools.build.os.path.exists", return_value=False), \
         patch("wechat_devtools_mcp.tools.build.socket.create_connection", side_effect=ConnectionRefusedError):
        result_str = await _action_compile(params)
        result = json.loads(result_str)
        assert result["success"] is True
        assert any("WXML" in e or "Bad attr" in e for e in result["data"]["wxml_errors"])


@pytest.mark.asyncio
async def test_compile_no_wxml_errors_when_clean():
    """编译成功且无 WXML 错误时，wxml_errors 为空列表。"""
    params = WechatBuildInput(action="compile", project_path="D:\\TestProject")
    cdp_clean = {"success": True, "data": []}

    with patch("wechat_devtools_mcp.tools.build._run_cli", new_callable=AsyncMock, return_value=_make_cli_success()), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=cdp_clean), \
         patch("wechat_devtools_mcp.tools.build._resolve_project_path", return_value="D:\\TestProject"), \
         patch("wechat_devtools_mcp.tools.build._detect_ide_port", return_value=None), \
         patch("wechat_devtools_mcp.tools.build.os.path.exists", return_value=False), \
         patch("wechat_devtools_mcp.tools.build.socket.create_connection", side_effect=ConnectionRefusedError):
        result_str = await _action_compile(params)
        result = json.loads(result_str)
        assert result["success"] is True
        assert result["data"]["wxml_errors"] == []


@pytest.mark.asyncio
async def test_compile_cdp_exception_silent():
    """CDP 采集抛出异常时不影响 compile 主流程。"""
    params = WechatBuildInput(action="compile", project_path="D:\\TestProject")

    with patch("wechat_devtools_mcp.tools.build._run_cli", new_callable=AsyncMock, return_value=_make_cli_success()), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, side_effect=Exception("connection refused")), \
         patch("wechat_devtools_mcp.tools.build._resolve_project_path", return_value="D:\\TestProject"), \
         patch("wechat_devtools_mcp.tools.build._detect_ide_port", return_value=None), \
         patch("wechat_devtools_mcp.tools.build.os.path.exists", return_value=False), \
         patch("wechat_devtools_mcp.tools.build.socket.create_connection", side_effect=ConnectionRefusedError):
        result_str = await _action_compile(params)
        result = json.loads(result_str)
        assert result["success"] is True
        assert result["data"]["wxml_errors"] == []


@pytest.mark.asyncio
async def test_compile_cdp_failure_silent():
    """CDP 采集失败时不影响 compile 主流程。"""
    params = WechatBuildInput(action="compile", project_path="D:\\TestProject")
    cdp_fail = {"success": False, "error": "Connection refused"}

    with patch("wechat_devtools_mcp.tools.build._run_cli", new_callable=AsyncMock, return_value=_make_cli_success()), \
         patch("wechat_devtools_mcp.tools.build._run_node_script", new_callable=AsyncMock, return_value=cdp_fail), \
         patch("wechat_devtools_mcp.tools.build._resolve_project_path", return_value="D:\\TestProject"), \
         patch("wechat_devtools_mcp.tools.build._detect_ide_port", return_value=None), \
         patch("wechat_devtools_mcp.tools.build.os.path.exists", return_value=False), \
         patch("wechat_devtools_mcp.tools.build.socket.create_connection", side_effect=ConnectionRefusedError):
        result_str = await _action_compile(params)
        result = json.loads(result_str)
        assert result["success"] is True
        assert result["data"]["wxml_errors"] == []
