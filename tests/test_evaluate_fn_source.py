"""evaluate 函数式签名（fn_source + args_json）与 expression 兼容路径。

TODO P1：旧实现把 expression 拼成 `return a(); b(); c()`，多语句静默只执行第一条。
新增 fn_source 从入参形态上消除歧义；expression 保留为单表达式入口，
daemon 回传 mode（expression / statement / function）供上层给出提示。
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import WechatAutomatorInput
from wechat_devtools_mcp.tools.automator import _action_evaluate, wechat_automator

TARGET = "wechat_devtools_mcp.tools.automator._run_node_script"


@pytest.mark.asyncio
async def test_fn_source_passes_fn_source_and_args():
    params = WechatAutomatorInput(
        action="evaluate",
        fn_source="function(a, b){ const s = a + b; return s; }",
        args_json="[1, 2]",
    )
    mock = AsyncMock(return_value={"success": True, "result": 3, "mode": "function"})
    with patch(TARGET, mock):
        resp = json.loads(await _action_evaluate(params))

    assert resp["success"] is True
    assert resp["data"]["result"] == 3
    assert resp["data"]["mode"] == "function"

    called = list(mock.call_args.args)
    assert called[0] == "ui_debug.js"
    assert "--fn-source" in called
    assert called[called.index("--fn-source") + 1] == params.fn_source
    assert "--args" in called
    assert called[called.index("--args") + 1] == "[1, 2]"
    assert "--code" not in called


@pytest.mark.asyncio
async def test_fn_source_without_args_omits_args_flag():
    params = WechatAutomatorInput(action="evaluate", fn_source="() => 1")
    mock = AsyncMock(return_value={"success": True, "result": 1, "mode": "function"})
    with patch(TARGET, mock):
        await _action_evaluate(params)
    called = list(mock.call_args.args)
    assert "--fn-source" in called
    assert "--args" not in called


@pytest.mark.asyncio
async def test_expression_only_uses_code_path():
    params = WechatAutomatorInput(action="evaluate", expression="1 + 2")
    mock = AsyncMock(return_value={"success": True, "result": 3, "mode": "expression"})
    with patch(TARGET, mock):
        resp = json.loads(await _action_evaluate(params))

    assert resp["success"] is True
    assert resp["data"]["result"] == 3
    called = list(mock.call_args.args)
    assert "--code" in called
    assert called[called.index("--code") + 1] == "1 + 2"
    assert "--fn-source" not in called


@pytest.mark.asyncio
async def test_fn_source_takes_precedence_over_expression():
    params = WechatAutomatorInput(action="evaluate", expression="1", fn_source="() => 2")
    mock = AsyncMock(return_value={"success": True, "result": 2, "mode": "function"})
    with patch(TARGET, mock):
        await _action_evaluate(params)
    called = list(mock.call_args.args)
    assert "--fn-source" in called
    assert "--code" not in called


@pytest.mark.asyncio
async def test_missing_both_returns_param_missing():
    params = WechatAutomatorInput(action="evaluate")
    mock = AsyncMock()
    with patch(TARGET, mock):
        resp = json.loads(await wechat_automator(params))

    assert resp["success"] is False
    assert resp["error_code"] == "PARAM_MISSING"
    assert "expression" in resp["message"] and "fn_source" in resp["message"]
    assert "fn_source" in resp.get("hint", "")
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_statement_mode_null_result_carries_hint():
    params = WechatAutomatorInput(action="evaluate", expression="const p = getCurrentPages(); p.length")
    mock = AsyncMock(return_value={"success": True, "result": None, "mode": "statement"})
    with patch(TARGET, mock):
        resp = json.loads(await _action_evaluate(params))

    assert resp["success"] is True
    assert resp["data"]["result"] is None
    assert resp["data"]["mode"] == "statement"
    assert "fn_source" in resp["data"]["hint"]
    assert "return" in resp["data"]["hint"]


@pytest.mark.asyncio
async def test_statement_mode_with_value_has_no_hint():
    params = WechatAutomatorInput(action="evaluate", expression="const p = [1]; return p.length")
    mock = AsyncMock(return_value={"success": True, "result": 1, "mode": "statement"})
    with patch(TARGET, mock):
        resp = json.loads(await _action_evaluate(params))
    assert "hint" not in resp["data"]


@pytest.mark.asyncio
async def test_evaluate_failure_propagates_error():
    params = WechatAutomatorInput(action="evaluate", expression="undefinedFn()")
    mock = AsyncMock(return_value={"success": False, "error": "undefinedFn is not defined"})
    with patch(TARGET, mock):
        resp = json.loads(await _action_evaluate(params))
    assert resp["success"] is False
    assert "undefinedFn" in resp["message"]
