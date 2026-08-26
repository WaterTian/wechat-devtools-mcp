"""navigate TabBar 页面自动检测测试。"""
import json
import os
import pytest
from unittest.mock import patch, AsyncMock

from wechat_devtools_mcp.tools.navigate import wechat_navigate, _get_tab_bar_pages
from wechat_devtools_mcp.models.schemas import WechatNavigateInput


def test_get_tab_bar_pages_parses_correctly(tmp_path):
    """正确解析 app.json 中的 tabBar.list。"""
    app_json = {
        "pages": ["pages/index/index", "pages/category/index", "pages/mine/index"],
        "tabBar": {
            "list": [
                {"pagePath": "pages/index/index", "text": "首页"},
                {"pagePath": "pages/category/index", "text": "分类"},
                {"pagePath": "pages/mine/index", "text": "我的"},
            ]
        }
    }
    app_json_path = tmp_path / "app.json"
    app_json_path.write_text(json.dumps(app_json), encoding="utf-8")
    result = _get_tab_bar_pages(str(app_json_path))
    assert result == {"pages/index/index", "pages/category/index", "pages/mine/index"}


def test_get_tab_bar_pages_no_tabbar(tmp_path):
    app_json = {"pages": ["pages/index/index"]}
    app_json_path = tmp_path / "app.json"
    app_json_path.write_text(json.dumps(app_json), encoding="utf-8")
    result = _get_tab_bar_pages(str(app_json_path))
    assert result == set()


def test_get_tab_bar_pages_file_not_found():
    result = _get_tab_bar_pages("/nonexistent/app.json")
    assert result == set()


@pytest.mark.asyncio
async def test_navigate_tabbar_page_uses_switch_tab(set_env_vars, tmp_path):
    """TabBar 页面应传递 --use-switch-tab 参数。"""
    app_json = {
        "pages": ["pages/index/index", "pages/detail/detail"],
        "tabBar": {"list": [{"pagePath": "pages/index/index", "text": "首页"}]}
    }
    (tmp_path / "app.json").write_text(json.dumps(app_json), encoding="utf-8")
    (tmp_path / "project.config.json").write_text(json.dumps({}), encoding="utf-8")

    fake_result = {
        "success": True, "cdp_available": False,
        "current_page": {"path": "pages/index/index", "query": {}},
        "cdp_logs": [], "page_data": {}, "current_page_timeout": False,
        "filtered_before_navigation": 0,
    }
    with patch("wechat_devtools_mcp.tools.navigate._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatNavigateInput(page_path="pages/index/index", project_path=str(tmp_path))
        result = json.loads(await wechat_navigate(params))

        call_args = mock_run.call_args[0]
        assert "--use-switch-tab" in call_args
        assert result["data"]["navigation_method"] == "switchTab"


@pytest.mark.asyncio
async def test_navigate_non_tabbar_page_uses_relaunch(set_env_vars, tmp_path):
    """非 TabBar 页面不传 --use-switch-tab。"""
    app_json = {
        "pages": ["pages/index/index", "pages/detail/detail"],
        "tabBar": {"list": [{"pagePath": "pages/index/index", "text": "首页"}]}
    }
    (tmp_path / "app.json").write_text(json.dumps(app_json), encoding="utf-8")
    (tmp_path / "project.config.json").write_text(json.dumps({}), encoding="utf-8")

    fake_result = {
        "success": True, "cdp_available": False,
        "current_page": {"path": "pages/detail/detail", "query": {}},
        "cdp_logs": [], "page_data": {}, "current_page_timeout": False,
        "filtered_before_navigation": 0,
    }
    with patch("wechat_devtools_mcp.tools.navigate._run_node_script", new_callable=AsyncMock, return_value=fake_result) as mock_run:
        params = WechatNavigateInput(page_path="pages/detail/detail", project_path=str(tmp_path))
        result = json.loads(await wechat_navigate(params))

        call_args = mock_run.call_args[0]
        assert "--use-switch-tab" not in call_args
        assert result["data"]["navigation_method"] == "reLaunch"
