"""CDP 端口的三件事：环境变量默认值、会话内粘性、端口占用者识别。

背景（2026-10-26，FanTown 真实使用核对）：9222 被本机常驻 sbot 自己起的 Chrome 长期占用，
agent 实际固定用 9333，但 inspector / navigate / compile 只要漏传 cdp_port 就连到 Chrome，
采到的全是别的网页；`open` 也不检查端口上是谁——Chrome 在听就当 IDE 就绪，再把 Chrome
页面的报错当成小程序启动错误返回（会话日志：「IDE 启动报 10 个错，全是阿里云/百度页面」）。
"""
import os
from typing import Any, Optional

# 默认 CDP 端口：环境变量 WECHAT_CDP_PORT 可改（9222 常年被 Chrome 占用的机器设成 9333）
DEFAULT_CDP_PORT: int = int(os.environ.get("WECHAT_CDP_PORT", "9222"))

# 本会话 `open` 成功用过的端口；其它工具不传 cdp_port 时沿用
_session_port: Optional[int] = None

# 只要 /json/list 里有任一 target 命中这些特征，就认定端口上是微信开发者工具：
#   /__pageframe__/、/appservice/      小程序渲染层 / 逻辑层（1.x 与 2.x 一致）
#   /app.asar/、electron-*.html         2.x(Electron) 外壳页
#   标题「小程序渲染层 / 小程序逻辑层 / 微信开发者工具」  2.x 标题；1.x 偶尔 url 字段就是窗口标题
_IDE_URL_MARKERS = (
    "/__pageframe__/", "/appservice/", "/app.asar/",
    "electron-entrance.html", "electron-project.html",
)
_IDE_TITLES = ("微信开发者工具", "小程序渲染层", "小程序逻辑层")


def remember_cdp_port(port: int) -> None:
    """`open` 成功后记住端口，供同会话其它工具沿用。"""
    global _session_port
    _session_port = int(port)


def forget_cdp_port() -> None:
    global _session_port
    _session_port = None


def session_cdp_port() -> Optional[int]:
    return _session_port


def resolve_cdp_port(params: Any) -> int:
    """显式传了 cdp_port 用显式值；否则沿用本会话 open 的端口；再否则 WECHAT_CDP_PORT / 9222。"""
    fields_set = getattr(params, "model_fields_set", set()) or set()
    if "cdp_port" in fields_set:
        return int(params.cdp_port)
    if _session_port:
        return _session_port
    return DEFAULT_CDP_PORT


def classify_cdp_targets(targets: Any) -> str:
    """按 /json/list 判断端口上是谁：'ide' / 'foreign' / 'empty'。"""
    if not isinstance(targets, list) or not targets:
        return "empty"
    for t in targets:
        if not isinstance(t, dict):
            continue
        url = str(t.get("url") or "")
        title = str(t.get("title") or "")
        if any(marker in url for marker in _IDE_URL_MARKERS):
            return "ide"
        if title in _IDE_TITLES or url in _IDE_TITLES:
            return "ide"
    return "foreign"


def describe_cdp_targets(targets: Any, limit: int = 3) -> list[str]:
    """给报错 / 诊断用的 target 摘要，形如 'page https://chatgpt.com/...'。"""
    out: list[str] = []
    if not isinstance(targets, list):
        return out
    for t in targets[:limit]:
        if isinstance(t, dict):
            label = str(t.get("url") or t.get("title") or "")[:80]
            out.append(f"{t.get('type', '?')} {label}".strip())
    return out
