import json
from unittest.mock import AsyncMock, patch

import pytest

from wechat_devtools_mcp.models.schemas import WechatInspectorInput
from wechat_devtools_mcp.tools.inspector import wechat_inspector
from wechat_devtools_mcp.utils.network_helpers import _format_network_requests


def _request_event(
    url="https://dig.example.test/track?evt=1&token=hidden",
    post_data='{"event":"View","token":"hidden"}',
    request_id="1",
):
    return {
        "type": "REQUEST",
        "timestamp": "2026-08-26T00:00:00Z",
        "targetType": "webview",
        "targetHint": "appservice",
        "content": {
            "requestId": request_id,
            "url": url,
            "method": "POST",
            "postData": post_data,
        },
    }


def test_network_schema_accepts_action_and_parameters():
    params = WechatInspectorInput(
        action="network", url_pattern=r"dig\.|track",
        include_responses=True, max_requests=12, appservice_only=False,
    )
    assert params.action == "network"
    assert params.max_requests == 12
    assert params.appservice_only is False


def test_network_formatter_merges_filters_and_redacts():
    raw_events = [
        _request_event(),
        {
            "type": "RESPONSE", "content": {
                "requestId": "1", "status": 200, "mimeType": "application/json",
            },
        },
        {
            "type": "FINISHED", "content": {"requestId": "1", "encodedDataLength": 123},
        },
        _request_event(url="https://unmatched.example.test/", post_data=None, request_id="2"),
    ]
    formatted = _format_network_requests(raw_events, r"dig\.example", True, True, 10)

    assert formatted["summary"] == {
        "total": 2, "matched": 1, "failed": 0, "truncated": False,
    }
    request = formatted["requests"][0]
    assert request["query"]["token"] == "***"
    assert "token=%2A%2A%2A" in request["url"]
    assert request["post_data"] == '{"event":"View","token":"***"}'
    assert request["status"] == 200
    assert request["mime_type"] == "application/json"
    assert request["encoded_data_length"] == 123


def test_network_formatter_omits_optional_data_and_reports_failures():
    formatted = _format_network_requests([
        _request_event(),
        {"type": "FAILED", "content": {"requestId": "1", "errorText": "net::ERR_FAILED"}},
    ], None, False, False, 10)

    request = formatted["requests"][0]
    assert "post_data" not in request
    assert "status" not in request
    assert request["error_text"] == "net::ERR_FAILED"
    assert formatted["summary"]["failed"] == 1


@pytest.mark.asyncio
async def test_network_forwards_collection_parameters():
    with patch(
        "wechat_devtools_mcp.tools.inspector._run_node_script",
        new_callable=AsyncMock,
        return_value={"success": True, "data": {"events": [], "network_enabled_targets": 1}},
    ) as mock_run:
        response = json.loads(await wechat_inspector(WechatInspectorInput(
            action="network", duration=7, cdp_port=9333, appservice_only=False,
        )))

    assert mock_run.call_args.args == (
        "network_listener.js", "--duration", "7", "--cdp-port", "9333",
        "--appservice-only", "false",
    )
    assert response["success"] is True
    assert response["data"]["summary"]["network_enabled_targets"] == 1


@pytest.mark.asyncio
async def test_network_maps_unavailable_cdp_to_specific_error():
    with patch(
        "wechat_devtools_mcp.tools.inspector._run_node_script",
        new_callable=AsyncMock,
        return_value={
            "success": False,
            "data": {"code": "CDP_UNAVAILABLE", "error": "ECONNREFUSED"},
        },
    ):
        response = json.loads(await wechat_inspector(WechatInspectorInput(action="network")))

    assert response["success"] is False
    assert response["error_code"] == "CDP_UNAVAILABLE"
