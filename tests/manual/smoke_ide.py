#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真机冒烟：按 SOP A 顺序把 7 个工具的主链路跑一遍，输出 JSON 报告。

不归 pytest 管（文件名不以 test_ 开头）。跨平台，Windows / macOS 都能跑。

用法（仓库根目录）：
    uv run python tests/manual/smoke_ide.py --cdp-port 9222 --out smoke.json
    环境变量 WECHAT_DEVTOOLS_CLI / WECHAT_PROJECT_PATH 必须已设置。

前置：IDE 已安装、服务端口已开、已扫码登录；项目路径指向一个能编译的小程序。
会做的事：kill 并重启 IDE（带 CDP）、开自动化端口、compile、跳一次页面、截两张图、quit 再拉起。
不会做的事：preview / upload / build_npm / cache_clean / 任何写业务数据的动作。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK
except Exception:
    pass

from wechat_devtools_mcp import __version__  # noqa: E402
from wechat_devtools_mcp.core import ide_state  # noqa: E402
from wechat_devtools_mcp.core.config import CLI_PATH  # noqa: E402
from wechat_devtools_mcp.core.node_bridge import _check_node_available  # noqa: E402
from wechat_devtools_mcp.models.schemas import (  # noqa: E402
    WechatAutomatorInput, WechatBuildInput, WechatFileInput, WechatIdeInput,
    WechatInspectorInput, WechatNavigateInput, WechatScreenshotInput,
)
from wechat_devtools_mcp.tools.automator import wechat_automator  # noqa: E402
from wechat_devtools_mcp.tools.build import wechat_build  # noqa: E402
from wechat_devtools_mcp.tools.file_reader import wechat_file  # noqa: E402
from wechat_devtools_mcp.tools.ide import wechat_ide  # noqa: E402
from wechat_devtools_mcp.tools.inspector import wechat_inspector  # noqa: E402
from wechat_devtools_mcp.tools.navigate import wechat_navigate  # noqa: E402
from wechat_devtools_mcp.tools.screenshot import wechat_screenshot  # noqa: E402

REPORT: dict = {"steps": [], "checkpoints": {}}


async def step(name: str, coro, keys=(), must=True):
    t0 = time.time()
    try:
        raw = await coro
        d = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        d = {"success": False, "message": f"{type(e).__name__}: {e}"}
    ms = int((time.time() - t0) * 1000)
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    picked = {k: data.get(k) for k in keys}
    entry = {"step": name, "ok": bool(d.get("success")), "ms": ms, "data": picked,
             "message": str(d.get("message") or d.get("error") or "")[:200]}
    if not entry["ok"]:
        entry["hint"] = d.get("hint")
        entry["error_code"] = d.get("error_code")
    REPORT["steps"].append(entry)
    mark = "OK " if entry["ok"] else "FAIL"
    print(f"[{mark}] {name:<28} {ms:>6}ms  {json.dumps(picked, ensure_ascii=False)[:150]}  | {entry['message'][:100]}")
    if must and not entry["ok"]:
        print("       ↑ 关键步骤失败，后续依赖它的步骤大概率也会失败；继续跑以收集证据。")
    return d


async def main(a):
    proj = os.environ.get("WECHAT_PROJECT_PATH", "")
    node_ok, node_path = await _check_node_available()
    REPORT["env"] = {
        "platform": sys.platform, "os": platform.platform(), "python": platform.python_version(),
        "mcp_version": __version__, "cli_path": CLI_PATH, "cli_exists": os.path.exists(CLI_PATH),
        "project_path": proj, "node": node_path, "cdp_port": a.cdp_port, "auto_port": a.auto_port,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print("ENV", json.dumps(REPORT["env"], ensure_ascii=False))
    cp = REPORT["checkpoints"]
    cp["1_cli_bat_exists"] = os.path.exists(CLI_PATH)

    pre = await step("status(pre)", wechat_ide(WechatIdeInput(action="status")),
                     ["ide_port", "service_port_enabled", "official_mcp"], must=False)
    cp["6_state_file_found_pre"] = (pre.get("data") or {}).get("ide_port") is not None

    if not a.skip_open:
        t_open = time.time()
        o = await step("open(cdp)", wechat_ide(WechatIdeInput(action="open", cdp_enabled=True, cdp_port=a.cdp_port)),
                       ["ide_runtime", "cdp_ready", "project_opened", "miniprogram_targets_ready", "startup_errors"])
        od = o.get("data") or {}
        cp["2_ide_runtime"] = od.get("ide_runtime")
        cp["4_cdp_ready"] = od.get("cdp_ready")
        cp["4_project_opened"] = od.get("project_opened")
        cp["4_miniprogram_targets_ready"] = od.get("miniprogram_targets_ready")
        cp["open_seconds"] = round(time.time() - t_open, 1)

    post = await step("status(post)", wechat_ide(WechatIdeInput(action="status")),
                      ["ide_port", "service_port_enabled", "official_mcp"], must=False)
    pd = post.get("data") or {}
    cp["6_state_file_found_post"] = pd.get("ide_port") is not None
    cp["official_mcp_available"] = (pd.get("official_mcp") or {}).get("available")

    t_start = time.time()
    for i in range(4):
        s = await step(f"start#{i+1}", wechat_automator(WechatAutomatorInput(action="start", auto_port=a.auto_port)),
                       ["verified", "cli_attempts", "retry_after_ms"])
        sd = s.get("data") or {}
        if s.get("success") and sd.get("verified"):
            break
        await asyncio.sleep((sd.get("retry_after_ms") or 5000) / 1000)
    cp["start_seconds"] = round(time.time() - t_start, 1)

    lp = await step("file.list_pages", wechat_file(WechatFileInput(action="list_pages")), ["total"], must=False)
    pages = [p.get("path") if isinstance(p, dict) else p for p in ((lp.get("data") or {}).get("pages") or [])]
    pi = await step("file.project_info", wechat_file(WechatFileInput(action="project_info")), ["project_path"], must=False)
    tabs = set()
    try:
        for t in (((pi.get("data") or {}).get("app_config") or {}).get("tabBar") or {}).get("list") or []:
            tabs.add(t.get("pagePath"))
    except Exception:
        pass
    target = a.page or next((p for p in pages if p not in tabs), None)

    await step("evaluate(fn_source+args)", wechat_automator(WechatAutomatorInput(
        action="evaluate", auto_port=a.auto_port,
        fn_source="(a,b)=>{const p=getCurrentPages();return {sum:a+b, depth:p.length, route:p[p.length-1]&&p[p.length-1].route}}",
        args_json="[2,3]")), ["result", "mode"])
    await step("evaluate(expression)", wechat_automator(WechatAutomatorInput(
        action="evaluate", auto_port=a.auto_port, expression="getCurrentPages().length")), ["result", "mode"], must=False)
    await step("evaluate(multi→statement)", wechat_automator(WechatAutomatorInput(
        action="evaluate", auto_port=a.auto_port, expression="var __a=1; var __b=2; __a+__b")), ["result", "mode", "hint"], must=False)
    await step("page_data", wechat_automator(WechatAutomatorInput(action="page_data", auto_port=a.auto_port)), ["path"], must=False)

    t_c = time.time()
    c = await step("compile", wechat_build(WechatBuildInput(action="compile", cdp_port=a.cdp_port)),
                   ["errors", "warnings", "automator_verified", "wxml_errors"])
    cp["compile_seconds"] = round(time.time() - t_c, 1)
    cp["compile_warnings_sample"] = ((c.get("data") or {}).get("warnings") or [])[:3]

    await step("inspector.cdp(5s)", wechat_inspector(WechatInspectorInput(action="cdp", duration=5, cdp_port=a.cdp_port)),
               ["summary"], must=False)
    out_dir = tempfile.gettempdir()
    await step("screenshot(full)", wechat_screenshot(WechatScreenshotInput(
        output_path=os.path.join(out_dir, "smoke_full.png"), full_page=True, auto_port=a.auto_port)),
        ["width", "height", "segments", "fixed_header", "fixed_footer", "truncated", "content_gaps"], must=False)
    if target:
        await step(f"navigate({target})", wechat_navigate(WechatNavigateInput(
            page_path=f"{target}?from=smoke", cdp_port=a.cdp_port, auto_port=a.auto_port, wait_ms=2500)),
            ["navigation_method", "current_page"], must=False)
        await step("page_data(expected)", wechat_automator(WechatAutomatorInput(
            action="page_data", auto_port=a.auto_port, expected_path=target)), ["path"], must=False)
    await step("screenshot(viewport)", wechat_screenshot(WechatScreenshotInput(
        output_path=os.path.join(out_dir, "smoke_viewport.png"), full_page=False, auto_port=a.auto_port)),
        ["width", "height"], must=False)

    if not a.skip_quit:
        q = await step("quit", wechat_ide(WechatIdeInput(action="quit")), ["exited"], must=False)
        cp["quit_exited"] = (q.get("data") or {}).get("exited")
        await asyncio.sleep(5)
        o2 = await step("open(cdp) after quit", wechat_ide(WechatIdeInput(action="open", cdp_enabled=True, cdp_port=a.cdp_port)),
                        ["ide_runtime", "cdp_ready", "project_opened"])
        cp["5_relaunch_after_quit_ok"] = bool(o2.get("success"))
        s2 = await step("start after relaunch", wechat_automator(WechatAutomatorInput(action="start", auto_port=a.auto_port)),
                        ["verified", "cli_attempts"], must=False)
        cp["start_after_relaunch_verified"] = (s2.get("data") or {}).get("verified")

    ok = sum(1 for s in REPORT["steps"] if s["ok"]); total = len(REPORT["steps"])
    REPORT["summary"] = {"passed": ok, "total": total, "failed": [s["step"] for s in REPORT["steps"] if not s["ok"]]}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2)
    print("\nCHECKPOINTS", json.dumps(cp, ensure_ascii=False))
    print(f"SUMMARY {ok}/{total} passed; failed={REPORT['summary']['failed']}\n报告已写入 {a.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cdp-port", type=int, default=9222)
    ap.add_argument("--auto-port", type=int, default=9420)
    ap.add_argument("--page", default=None, help="navigate 目标页（非 tabBar 页），默认自动从 list_pages 挑第一个")
    ap.add_argument("--skip-open", action="store_true", help="不重启 IDE，用当前已打开的窗口")
    ap.add_argument("--skip-quit", action="store_true", help="跳过 quit → 重新拉起 这一段")
    ap.add_argument("--out", default="smoke.json")
    args = ap.parse_args()
    for var in ("WECHAT_DEVTOOLS_CLI", "WECHAT_PROJECT_PATH"):
        if not os.environ.get(var):
            sys.exit(f"缺少环境变量 {var}")
    asyncio.run(main(args))
