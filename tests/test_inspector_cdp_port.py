"""inspector(action='cdp') 必须把 cdp_port 透传给 cdp_listener.js。

背景：schema 对外暴露了 cdp_port（默认 9222，可配 1~65535），但 _action_cdp 只传了
duration，cdp_listener.js 的位置参数第二位拿不到值 → 永远连 9222。
参数看似可配实则失效，调用方改了端口也无感知。

cdp_listener.js 的兼容位置参数约定：argv[2]=duration, argv[3]=cdp_port。
daemon 拼 fakeArgv = ['node','daemon.js', ...rawArgs]，故 rawArgs[0]→duration、rawArgs[1]→cdp_port。
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import WechatInspectorInput
from wechat_devtools_mcp.tools.inspector import wechat_inspector


@pytest.mark.asyncio
async def test_custom_cdp_port_is_forwarded():
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=[]) as mock_run:
        params = WechatInspectorInput(action="cdp", duration=5, cdp_port=9333)
        await wechat_inspector(params)

        args = mock_run.call_args[0]
        assert args[0] == "cdp_listener.js"
        assert args[1] == "5"
        assert args[2] == "9333", f"cdp_port 未透传，实际参数：{args}"


@pytest.mark.asyncio
async def test_default_cdp_port_is_forwarded():
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=[]) as mock_run:
        params = WechatInspectorInput(action="cdp", duration=3)
        await wechat_inspector(params)

        args = mock_run.call_args[0]
        assert args[1] == "3"
        assert args[2] == "9222"


@pytest.mark.asyncio
async def test_cdp_reads_daemon_data_key():
    """daemon 把 handler 返回的数组放在 data 下，inspector 必须读得到。

    回归防护：v0.9.0 daemon 架构起 _run_node_script 统一把 list 结果包成
    {"success": True, "data": [...]}，而 _action_cdp 读的是 result["logs"]，
    该 key 根本不存在 → cdp 采集恒返回 0 条，静默失灵了 8 个小版本。
    （ide.py / build.py 读的都是 data，只有 inspector 读错。）
    """
    raw = [{
        "type": "RUNTIME_CONSOLE", "url": "http://127.0.0.1/appservice/mainframe",
        "content": {"type": "error", "args": ["daemon data key"]},
    }]
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value={"success": True, "data": raw}):
        result = json.loads(await wechat_inspector(
            WechatInspectorInput(action="cdp", duration=3)))
        assert result["success"] is True
        assert result["data"]["summary"]["errors"] == 1, "data 下的日志被丢弃了"
        assert "daemon data key" in json.dumps(result, ensure_ascii=False)


@pytest.mark.asyncio
async def test_cdp_reads_legacy_logs_key():
    """旧形态 {"logs": [...]} 仍需兼容。"""
    raw = [{
        "type": "RUNTIME_CONSOLE", "url": "http://127.0.0.1/appservice/mainframe",
        "content": {"type": "error", "args": ["legacy logs key"]},
    }]
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value={"success": True, "logs": raw}):
        result = json.loads(await wechat_inspector(
            WechatInspectorInput(action="cdp", duration=3)))
        assert result["data"]["summary"]["errors"] == 1


@pytest.mark.asyncio
async def test_cdp_result_still_parsed():
    """透传参数不得影响原有返回值解析。"""
    raw = [{
        "type": "RUNTIME_CONSOLE", "url": "http://127.0.0.1/appservice/mainframe",
        "timestamp": "2026-08-19T00:00:00.000Z",
        "content": {"type": "error", "args": ["boom"]},
    }]
    with patch("wechat_devtools_mcp.tools.inspector._run_node_script",
               new_callable=AsyncMock, return_value=raw):
        params = WechatInspectorInput(action="cdp", duration=5, cdp_port=9444)
        result = json.loads(await wechat_inspector(params))
        assert result["success"] is True
        assert result["data"]["summary"]["errors"] == 1
