"""automator start 连接验证逻辑测试（v0.9.5 起 verified = TCP && WS）。
v0.9.8 _action_start 改用 _run_cli 替代 subprocess.Popen。

WS 级验证改为按截止时间轮询（2026-10-26 真机 2.02.2608060 实测）：
`cli auto` 后 2.4s WS 即可连，但 `currentPage` 要 ~9s（冷启动 ~11s）才首次应答；
旧实现「10s 预算 × 2 次」卡在边缘，稍有负载就把「还没准备好」报成
「TCP 已监听但 WebSocket 握手未完成」——FanTown 9 月至 10 月会话里反复出现的那条。
"""
import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from wechat_devtools_mcp.tools import automator
from wechat_devtools_mcp.tools.automator import (
    wechat_automator,
    _verify_port_ready,
    _verify_ws_ready,
)
from wechat_devtools_mcp.models.schemas import WechatAutomatorInput


def _fake_clock(step: float):
    """替换 automator._monotonic：每次读表前进 step 秒，让截止时间循环在测试里可终止。"""
    state = {"t": 0.0}

    def _now():
        state["t"] += step
        return state["t"]
    return _now


def _mock_cli_success():
    """_run_cli 返回 CLI 成功的结果。"""
    return {"success": True, "stdout": "", "stderr": "", "return_code": 0}


def _mock_cli_failure():
    """_run_cli 返回 CLI 失败的结果。"""
    return {"success": False, "stdout": "", "stderr": "CLI failed", "return_code": 1}


@pytest.mark.asyncio
async def test_start_returns_ready_when_tcp_and_ws_ok():
    """CLI + TCP + WS 都通过时 verified=true，message 含 '已就绪'。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=True):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is True
        assert data["data"]["verified"] is True
        assert data["data"]["tcp_ready"] is True
        assert data["data"]["ws_ready"] is True
        assert data["data"]["verify_attempts"] == 1
        assert "已就绪" in data["message"]


@pytest.mark.asyncio
async def test_start_cli_fail_returns_error():
    """CLI auto 失败时立即返回 _fail，不等 TCP。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_failure()):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is False
        assert "CLI auto 执行失败" in data["message"]


@pytest.mark.asyncio
async def test_start_tcp_fail_returns_error():
    """CLI 成功但 TCP 未监听时返回 _fail。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()) as cli, \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=False), \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep", new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)
        assert data["success"] is False
        # 2026-09-03 起 cli auto 最多重试 3 轮再放弃
        assert cli.await_count == 3
        assert "未监听" in data["message"]


@pytest.mark.asyncio
async def test_start_ws_fail_triggers_invalidate_and_retry():
    """TCP OK 但 WS 第一次失败时应 invalidate + 2s + 再试，共 2 次。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
    ws_results = [False, True]

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, side_effect=ws_results) as mock_ws, \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True) as mock_inv, \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)

        assert data["data"]["verified"] is True
        assert data["data"]["verify_attempts"] == 2
        assert mock_ws.call_count == 2
        assert mock_inv.call_count == 1


@pytest.mark.asyncio
async def test_start_ws_never_ready_polls_until_deadline(monkeypatch):
    """TCP OK 但 WS 一直不应答：按截止时间（默认 45s）轮询，到期返回 verified=false + retry_after_ms。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
    # 每次读表前进 20s：t0=20，探测后 40、60 → 第 3 次探测后越过 45s 截止
    monkeypatch.setattr(automator, "_monotonic", _fake_clock(20))

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=False) as mock_ws, \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True) as mock_inv, \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        response = await _action_start(params)
        data = json.loads(response)

        assert data["data"]["verified"] is False
        assert data["data"]["tcp_ready"] is True
        assert data["data"]["ws_ready"] is False
        assert data["data"]["retry_after_ms"] == 3000
        assert data["data"]["verify_attempts"] == 3
        assert mock_ws.call_count == 3
        assert mock_inv.call_count == 2, "每次失败后都要清掉半死的缓存连接，最后一次到期不再清"
        assert data["data"]["ready_timeout_s"] == 45
        assert data["data"]["waited_ms"] >= 45_000
        # 提示必须先让调用方重试 start（不重启 IDE），open 只能是最后手段
        assert "start" in data["data"]["hint"]
        assert data["data"]["hint"].index("start") < data["data"]["hint"].index("open")


@pytest.mark.asyncio
async def test_start_honors_ready_timeout_param(monkeypatch):
    """ready_timeout 参数覆盖默认截止时间。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project", ready_timeout=5)
    monkeypatch.setattr(automator, "_monotonic", _fake_clock(6))  # t0=6，探测后 12 → 已过 5s

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=False) as mock_ws, \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        data = json.loads(await _action_start(params))

        assert data["data"]["verified"] is False
        assert data["data"]["ready_timeout_s"] == 5
        assert mock_ws.call_count == 1
        assert "5" in data["message"]


@pytest.mark.asyncio
async def test_start_reports_ready_after_ms():
    """就绪时报告等了多久（真机 cli auto 后约 7~11s 才首次应答，调用方据此判断是否正常）。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()), \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, return_value=True):
        data = json.loads(await _action_start(params))

        assert data["data"]["verified"] is True
        assert isinstance(data["data"]["ready_after_ms"], int)
        assert data["data"]["ready_after_ms"] >= 0


def test_ready_timeout_schema_bounds():
    """ready_timeout 默认 None（取环境变量/45），范围 5~180。"""
    from pydantic import ValidationError

    assert WechatAutomatorInput(action="start").ready_timeout is None
    assert WechatAutomatorInput(action="start", ready_timeout=90).ready_timeout == 90
    with pytest.raises(ValidationError):
        WechatAutomatorInput(action="start", ready_timeout=4)
    with pytest.raises(ValidationError):
        WechatAutomatorInput(action="start", ready_timeout=181)


@pytest.mark.asyncio
async def test_verify_ws_ready_calls_automation_js_pagestack():
    """_verify_ws_ready 必须调用 automation.js pageStack（驼峰），不是 ui_debug.js。"""
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, return_value={"success": True}) as mock_run:
        await _verify_ws_ready(9420)
        args = mock_run.call_args[0]
        assert args[0] == "automation.js"
        assert "pageStack" in args
        assert "page_stack" not in args


@pytest.mark.asyncio
async def test_verify_ws_ready_timeout_covers_daemon_health_check():
    """单次探测的 Python 超时必须盖过 daemon 新连接健康检查上限（≈20s）。

    旧值 10s：daemon 还在第 3 轮 currentPage 重试，Python 已超时放弃，
    连接被遗弃、下一次探测再起一个新连接——真机上 currentPage 要 7~11s 才首答，
    这正是「TCP 已监听但 WebSocket 握手未完成」的来源。
    """
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, return_value={"success": True}) as mock_run:
        await _verify_ws_ready(9420)
        assert mock_run.call_args.kwargs["timeout"] >= 25


@pytest.mark.asyncio
async def test_verify_ws_ready_returns_false_on_exception():
    with patch("wechat_devtools_mcp.tools.automator._run_node_script",
               new_callable=AsyncMock, side_effect=RuntimeError("daemon down")):
        assert await _verify_ws_ready(9420) is False


@pytest.mark.asyncio
async def test_verify_port_ready_max_attempts_5():
    """_verify_port_ready 默认 max_attempts=20，_action_start 传入 5。"""
    with patch("wechat_devtools_mcp.tools.automator.socket") as mock_socket:
        mock_socket.create_connection.side_effect = ConnectionRefusedError
        with patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
                   new_callable=AsyncMock) as mock_sleep:
            result = await _verify_port_ready(9420, max_attempts=5)
            assert result is False
            assert mock_sleep.call_count == 5


@pytest.mark.asyncio
async def test_start_reruns_cli_auto_when_ws_stays_silent(monkeypatch):
    """WS 静默超过 15s 自动再跑一次 cli auto（真机：第二次 cli auto 7s 就活）。"""
    from wechat_devtools_mcp.tools.automator import _action_start

    params = WechatAutomatorInput(action="start", project_path="D:/fake/project")
    # 每次读表前进 10s：t0=10；第 1 次失败 now=20（距上次 cli 10s，不重跑）；第 2 次失败 now=30（20s，重跑）；第 3 次成功
    monkeypatch.setattr(automator, "_monotonic", _fake_clock(10))

    with patch("wechat_devtools_mcp.tools.automator._run_cli",
               new_callable=AsyncMock, return_value=_mock_cli_success()) as cli, \
         patch("wechat_devtools_mcp.tools.automator._verify_port_ready",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator._verify_ws_ready",
               new_callable=AsyncMock, side_effect=[False, False, True]), \
         patch("wechat_devtools_mcp.tools.automator.invalidate_connection",
               new_callable=AsyncMock, return_value=True), \
         patch("wechat_devtools_mcp.tools.automator.asyncio.sleep",
               new_callable=AsyncMock):
        data = json.loads(await _action_start(params))

    assert data["data"]["verified"] is True
    assert cli.await_count == 2, "首跑 + 静默 15s 后的一次重跑"
    assert data["data"]["cli_attempts"] == 2
    assert data["data"]["verify_attempts"] == 3
