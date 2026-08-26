"""wechat_ide status action 测试：验证 mcp_version 字段。"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.tools.ide import _action_status


@pytest.mark.asyncio
async def test_status_returns_mcp_version():
    """status 返回的 data 中应包含 mcp_version 字段。"""
    with patch(
        "wechat_devtools_mcp.tools.ide._check_node_available",
        new_callable=AsyncMock,
        return_value=(True, "/usr/bin/node"),
    ):
        result = json.loads(await _action_status())
        assert result["success"] is True
        assert "mcp_version" in result["data"]
        # 版本号应匹配 __init__.py 中的值
        from wechat_devtools_mcp import __version__
        assert result["data"]["mcp_version"] == __version__
