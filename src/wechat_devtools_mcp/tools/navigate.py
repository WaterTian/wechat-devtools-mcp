"""
wechat_navigate 工具：跳转页面并采集 CDP 日志（独立工具，无 action 参数）。

保持独立是因为它横跨自动化（automator）和 CDP 两个领域，是高频跨领域操作。
"""
import json
import os
from typing import TYPE_CHECKING

from ..core.errors import ErrorCode
from ..core.config import DEFAULT_PROJECT_PATH
from ..core.node_bridge import _run_node_script
from ..models.schemas import WechatNavigateInput
from ..utils.cdp_helpers import _format_cdp_logs_v2
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP


def _get_tab_bar_pages(app_json_path: str) -> set[str]:
    """读取 app.json，解析 tabBar.list[].pagePath，返回 pagePath 集合（不带前导 /）。"""
    try:
        with open(app_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tab_bar = data.get("tabBar", {})
        items = tab_bar.get("list", [])
        return {item["pagePath"].lstrip("/") for item in items if "pagePath" in item}
    except Exception:
        return set()


def _get_miniprogram_root(proj: str) -> str:
    """读取 project.config.json，返回小程序根目录的绝对路径。"""
    try:
        config_path = os.path.join(proj, "project.config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        mp_root = config.get("miniprogramRoot", "")
        if mp_root:
            return os.path.join(proj, mp_root)
    except Exception:
        pass
    return proj


def register_navigate(mcp: "FastMCP") -> None:
    """将 wechat_navigate 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_navigate",
        annotations={
            "title": "跳转页面并采集 CDP 日志",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_navigate)


async def wechat_navigate(params: WechatNavigateInput) -> str:
    """跳转到指定页面，等待指定时间，通过 CDP 采集高清日志。
    适用于页面生命周期日志检查（onLoad/onShow）、页面错误验证。
    需先调用 wechat_automator(action='start') 并以 cdp_enabled=true 打开项目。
    返回 JSON: {success, data: {current_page, cdp_logs}, message}。
    """
    try:
        page = params.page_path
        if not page.startswith("/"):
            page = "/" + page

        wait_seconds = params.wait_ms / 1000
        total_timeout = max(params.timeout, int(wait_seconds) + 10)

        # ── TabBar 自动检测 ──
        is_tab_page = False
        try:
            proj = params.project_path or DEFAULT_PROJECT_PATH
            if proj:
                mp_root = _get_miniprogram_root(proj)
                app_json_path = os.path.join(mp_root, "app.json")
                tab_pages = _get_tab_bar_pages(app_json_path)
                # 去掉前导 / 和 query 参数后比较
                page_bare = page.lstrip("/").split("?")[0]
                is_tab_page = page_bare in tab_pages
        except Exception:
            pass

        js_args = [
            "navigate_capture.js",
            "--port", str(params.auto_port),
            "--page", page,
            "--wait", str(params.wait_ms),
            "--cdp-port", str(params.cdp_port),
            "--clear-logs", str(params.clear_logs).lower(),
        ]
        if is_tab_page:
            js_args.append("--use-switch-tab")

        result = await _run_node_script(
            *js_args,
            timeout=total_timeout,
        )

        if not result.get("success") and "error" in result and not result.get("cdp_logs"):
            return _fail(
                ErrorCode.UNKNOWN_ERROR,
                f"跳转失败：{result['error']}",
                hint="请确认已调用 wechat_automator(action='start') 并以 cdp_enabled=true 打开项目。",
            )

        # CDP 日志结构化
        raw_cdp = result.get("cdp_logs", [])
        formatted_cdp = _format_cdp_logs_v2(raw_cdp, params.detail_level, params.max_logs)

        error_cnt = formatted_cdp["summary"]["errors"]
        warn_cnt = formatted_cdp["summary"]["warnings"]

        data = {
            "page": page,
            "wait_ms": params.wait_ms,
            "navigation_method": "switchTab" if is_tab_page else "reLaunch",
            "cdp_available": result.get("cdp_available", False),
            "current_page": result.get("current_page"),
            "cdp_logs": formatted_cdp,
            "logs_since": result.get("logs_since"),
            "filtered_before_navigation": result.get("filtered_before_navigation", 0),
        }

        # 页面路径不匹配提示
        if result.get("navigation_mismatch"):
            data["navigation_mismatch"] = True

        filtered = result.get("filtered_before_navigation", 0)
        filter_note = f"（已过滤 {filtered} 条历史日志）" if filtered > 0 else ""
        msg = f"已跳转至 {page}，发现 {error_cnt} 个错误、{warn_cnt} 个警告。{filter_note}"

        if result.get("navigation_mismatch"):
            actual = result.get("current_page", {}).get("path", "unknown") if result.get("current_page") else "unknown"
            msg += (
                f" ⚠ 页面跳转后路径不匹配（期望 {page}，实际 {actual}），"
                "建议使用 wechat_automator(action='evaluate', "
                f"expression=\"wx.switchTab({{url:'{page.split('?')[0]}'}});'ok'\") 手动跳转"
            )

        # current_page 超时提示
        if result.get("current_page_timeout"):
            msg += " ⚠ 页面栈未就绪，current_page 为 null，页面可能仍在初始化。"

        # ── page_data 诊断（可选）──
        if params.check_data and "?" in params.page_path:
            page_data = result.get("page_data")
            if page_data and isinstance(page_data, dict):
                fields = list(page_data.values())
                if len(fields) >= 5:
                    empty_count = sum(
                        1 for v in fields
                        if v is None or v == "" or v == [] or v == "undefined"
                    )
                    if empty_count / len(fields) > 0.7:
                        data["warning"] = (
                            "页面数据大部分为空，可能是 query 参数名错误。"
                            "建议：使用 wechat_file(action='read_page') 查看页面 onLoad 方法确认正确的参数名。"
                        )
                        msg += " ⚠ 疑似参数名错误，详见 warning 字段。"

        return _ok(data, message=msg)

    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")
