"""wechat_ide status：探测开发者工具 2.x 内建 MCP 服务（TODO P6 第 1 步）。

事实（2026-08-28 实测，2026-09-03 复核）：IDE 2.x 在 ``http://127.0.0.1:<idePort>/mcp``
内建 Streamable HTTP MCP Server，``GET /mcp/heartbeat`` 返回
``{"ok":true,"service":"mcp","running":true,"port":<idePort>,"sessions":0}``。
2.x 自 2026-08-18 起是官方 Stable，因此所有升级用户都同时拥有官方 46 工具与本项目 7 工具；
status 必须把这件事报出来，SKILL 才能据此分流。

探测只读：不做 ``initialize``（那会在 IDE 侧登记一条已授权客户端记录）。
"""
import http.server
import json
import socket
import threading
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.tools import ide


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Heartbeat(http.server.BaseHTTPRequestHandler):
    payload = {"ok": True, "service": "mcp", "running": True, "port": 0, "sessions": 2}

    def do_GET(self):
        if self.path != "/mcp/heartbeat":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def heartbeat_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Heartbeat)
    _Heartbeat.payload = dict(_Heartbeat.payload, port=server.server_port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server.server_port
    server.shutdown()


class TestProbeOfficialMcp:

    @pytest.mark.asyncio
    async def test_parses_heartbeat(self, heartbeat_server):
        info = await ide._probe_official_mcp(heartbeat_server)
        assert info is not None
        assert info["ok"] is True
        assert info["sessions"] == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_port_closed(self):
        info = await ide._probe_official_mcp(_free_port())
        assert info is None


class TestStatusOfficialMcpField:

    @pytest.mark.asyncio
    async def test_reports_available_when_heartbeat_ok(self, monkeypatch):
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 11071)
        monkeypatch.setattr(ide.ide_state, "read_service_port_enabled", lambda: True)
        probe = AsyncMock(return_value={"ok": True, "service": "mcp", "running": True,
                                        "port": 11071, "sessions": 0})
        monkeypatch.setattr(ide, "_probe_official_mcp", probe)
        with patch("wechat_devtools_mcp.tools.ide._check_node_available",
                   new_callable=AsyncMock, return_value=(True, "node")):
            result = json.loads(await ide._action_status())

        probe.assert_awaited_once_with(11071)
        official = result["data"]["official_mcp"]
        assert official["available"] is True
        assert official["port"] == 11071
        assert official["running"] is True
        assert official["sessions"] == 0
        # 消息里要提示分流，SKILL 依赖这条判断
        assert "内建 MCP" in result["message"]

    @pytest.mark.asyncio
    async def test_unavailable_without_ide_port(self, monkeypatch):
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: None)
        monkeypatch.setattr(ide.ide_state, "read_service_port_enabled", lambda: None)
        probe = AsyncMock()
        monkeypatch.setattr(ide, "_probe_official_mcp", probe)
        with patch("wechat_devtools_mcp.tools.ide._check_node_available",
                   new_callable=AsyncMock, return_value=(True, "node")):
            result = json.loads(await ide._action_status())

        probe.assert_not_awaited()
        official = result["data"]["official_mcp"]
        assert official["available"] is False
        assert official["port"] is None

    @pytest.mark.asyncio
    async def test_unavailable_when_probe_fails(self, monkeypatch):
        """1.06 或 IDE 未启动：端口读得到但心跳不通 → available False，不报错。"""
        monkeypatch.setattr(ide.ide_state, "read_ide_port", lambda: 11071)
        monkeypatch.setattr(ide.ide_state, "read_service_port_enabled", lambda: True)
        monkeypatch.setattr(ide, "_probe_official_mcp", AsyncMock(return_value=None))
        with patch("wechat_devtools_mcp.tools.ide._check_node_available",
                   new_callable=AsyncMock, return_value=(True, "node")):
            result = json.loads(await ide._action_status())

        assert result["success"] is True
        assert result["data"]["official_mcp"] == {
            "available": False, "port": 11071, "running": None, "sessions": None,
        }
