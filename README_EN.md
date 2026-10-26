# WeChat DevTools MCP Server (v0.9.19)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![中文文档](https://img.shields.io/badge/lang-中文文档-red.svg)](./README.md)

> Wraps WeChat DevTools as an [MCP](https://modelcontextprotocol.io/) server so the AI in your editor can **compile, preview, debug and auto-test** Mini Programs end to end. Windows / macOS, listed in the official MCP Registry.

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

> [!IMPORTANT]
> "Lean MCP + Rich Skill": the server exposes only 7 aggregated tools; workflows and best practices live in the companion [wechat-devtools Skill](#step-5--install-the-skill-required). **Install both.**

---

## 🤝 Relationship to WeChat's Built-in Capabilities

WeChat DevTools **2.x has been the official Stable channel since 2026-08-18** (1.06 is no longer offered). The IDE ships a built-in MCP server (47 atomic tools, 2 of them deprecated). The two are complementary, not substitutes:

| Scenario | Use |
|----------|-----|
| Open project / compile / preview / upload / tap & input / cloud | On 2.x prefer the built-in MCP (`wechat_ide(action='status')` reports `official_mcp.available: true` when reachable) |
| **Stitched long-page screenshots** (fixed header/footer detection, honest reporting when incomplete) | This project. The official tool captures the viewport only, downsized to a 1280px JPEG |
| **Structured CDP logs** (replays history from before the capture, grouped by page, noise filtered) | This project. Official log tools read a cached buffer only |
| **Task-level SOPs** (one-shot page inspection / exception triage / cross-page checks) | This project's Skill |
| Existing 1.06.x (NW.js) installs | Still supported here; the built-in MCP exists only on 2.x |

> ⚠ The IDE registers its own bridge as `wechat-devtools`. Every example here uses **`wechat-devtools-mcp`** to avoid the clash; old-name configs keep working and only matter when both servers share one agent.

---

## 🚀 Quick Start

**Prerequisites**: Python ≥ 3.10 (`uv` provisions it), Node.js ≥ 18 (the daemon depends on puppeteer-core / jimp), WeChat DevTools 2.x or 1.06.x.

### Step 1 — Install the MCP Server

```bash
pip install uv                                           # or brew install uv; skip if installed
uv tool install wechat-devtools-mcp                      # first install
uv tool install wechat-devtools-mcp --force --refresh    # upgrade: --refresh bypasses the index cache, otherwise an old version may come back
wechat-devtools-mcp --version                            # confirm the running version
```

> [!WARNING]
> If an older version was installed with `pip install`, run `pip uninstall wechat-devtools-mcp` first; the pip path shadows uv's.
> ≤0.9.10 is incompatible with mcp SDK ≥2.0 (`ModuleNotFoundError: mcp.server.fastmcp`); upgrade to ≥0.9.11.

Stop the MCP process running inside your editor before upgrading (restarting the editor is enough). Clients configured with `uvx` reuse the cached environment and **do not upgrade on their own**: run `uvx --refresh wechat-devtools-mcp --version` once, or pin `wechat-devtools-mcp==X.Y.Z` in `args`.

### Step 2 — Enable the DevTools Service Port

`DevTools` → `Settings` → `Security` → `Service Port` → `Enable`. Without it every CLI-backed call (`open`, `compile`, `preview`, ...) fails with `CLI_TIMEOUT`.

### Step 3 — Prepare Two Absolute Paths

| Path | Windows | macOS |
|------|---------|-------|
| DevTools CLI | `C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat` | `/Applications/wechatwebdevtools.app/Contents/MacOS/cli` |
| Mini Program project root | `D:\MyProjects\mini-app` | `/Users/<you>/Projects/mini-app` |

Escape Windows `\` as `\\` in JSON; macOS `/` needs no escaping.

### Step 4 — Editor Configuration

Standard config (works for Claude Desktop / Antigravity / Kiro / Trae / Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "wechat-devtools-mcp": {
      "command": "uvx",
      "args": ["wechat-devtools-mcp"],
      "env": {
        "WECHAT_DEVTOOLS_CLI": "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat",
        "WECHAT_PROJECT_PATH": "D:\\Your\\Project\\Path"
      }
    }
  }
}
```

On machines where port 9222 is permanently held by Chrome, add `"WECHAT_CDP_PORT": "9333"` to `env`.

| Editor | Where | Differences |
|--------|-------|-------------|
| Claude Desktop / Antigravity | `claude_desktop_config.json` / `mcp_config.json` | none |
| Claude Code (per project) | `.mcp.json` in the repo root | `uvx` from the terminal PATH is enough. Only if a GUI-launched editor (desktop app) cannot find `uvx` / `node`: use the absolute `command` `/opt/homebrew/bin/uvx` and add `"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"` plus `"NODE_PATH": "/opt/homebrew/bin/node"` to `env` |
| Kiro | `~/.kiro/settings/mcp.json` | optional `"autoApprove": ["wechat_ide","wechat_build","wechat_automator","wechat_inspector","wechat_screenshot","wechat_navigate","wechat_file"]` |
| Trae ≥1.3 | AI panel → Settings → MCP → Manual; or `%APPDATA%\Trae\User\globalStorage\mcp.json` / `~/Library/Application Support/Trae/User/globalStorage/mcp.json` | Chat must use the **Builder with MCP** agent; on macOS use the same absolute paths if `uvx` is not found |
| Cursor / VS Code | Add a server in the MCP panel | Name `wechat-devtools-mcp`, Command `uvx wechat-devtools-mcp`, same env vars |
| OpenAI Codex | `~/.codex/config.toml` | TOML, see below |

```toml
[mcp_servers.wechat-devtools-mcp]
command = "uvx"
args = ["wechat-devtools-mcp"]

[mcp_servers.wechat-devtools-mcp.env]
WECHAT_DEVTOOLS_CLI = "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat"
WECHAT_PROJECT_PATH = "D:\\Your\\Project\\Path"
```

### Step 5 — Install the Skill (Required)

```bash
npx -y skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
```

For clients without `npx skills` (e.g. Trae), copy the repo's `.agents/skills/wechat-devtools/` into your project's `.agents/skills/`. The Skill provides 9 SOPs, a full action reference for all 7 tools, a progressive CDP strategy and a troubleshooting table; see [SKILL.md](./.agents/skills/wechat-devtools/SKILL.md).

### Step 6 — Self-check

Call `wechat_ide(action='status')` once from your editor and make sure these match before starting:

| Field | Expected | Otherwise |
|-------|----------|-----------|
| `cli_exists` / `project_exists` / `node_available` | `true` | Re-check the two paths from Step 3; install Node.js ≥ 18 |
| `service_port_enabled` | `true` | See Step 2 |
| `cdp_port_occupant.kind` | `none` or `ide` | `foreign` means another browser holds the port; set `WECHAT_CDP_PORT=9333` |
| `skill_version` | equals `mcp_version` | Re-run Step 5 to refresh the skill copy |

---

## 🛠️ Toolbox

| Tool | Purpose | actions / key params |
|------|---------|----------------------|
| `wechat_ide` | IDE lifecycle & diagnostics | `open` `login` `is_login` `close` `quit` `status` |
| `wechat_build` | Build & publish | `compile` `preview` `upload` `build_npm` `cache_clean` |
| `wechat_automator` | Automation & runtime queries | `start` `tap` `input` `element_info` `set_data` `call_method` `call_wx` `mock_wx` `evaluate` `page_stack` `page_data` `system_info` `storage` |
| `wechat_inspector` | Runtime log capture | `console` `cdp` |
| `wechat_screenshot` | Stitched long-page screenshots | `full_page` `page_path` `scroll_top` |
| `wechat_navigate` | Navigate and capture CDP logs | `page_path` |
| `wechat_file` | Project file reading | `project_info` `list_pages` `read_page` `read_file` |

When an action hits an automator connection failure it runs `start` once and retries (reported as `auto_recovered`); after a successful `open` the `cdp_port` is reused for the session, so the other tools need not pass it. Full parameters: [MCP_DOC.md](./MCP_DOC.md). Cloud functions and databases: use [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit).

---

## 💡 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WECHAT_DEVTOOLS_CLI` | DevTools CLI path (**required**) | — |
| `WECHAT_PROJECT_PATH` | Default project root (**required**) | — |
| `WECHAT_CLI_TIMEOUT` | CLI timeout in seconds | `30` |
| `WECHAT_CDP_PORT` | Default CDP debugging port. Set to `9333` when 9222 is held by Chrome; after a successful `open` the other tools reuse that port for the session | `9222` |
| `WECHAT_AUTOMATOR_READY_TIMEOUT` | Seconds `start` waits for the automator to answer; raise it for large projects on cold start | `45` |
| `NODE_PATH` | Node.js executable | `node` |

---

## ❓ FAQ

| Symptom | Fix |
|---------|-----|
| Constant `CLI_TIMEOUT` | Service port is off, see Step 2; `wechat_ide(action='status')` exposes `service_port_enabled` |
| CDP capture fails / only other web pages show up | `status` reports `cdp_port_occupant.kind: foreign`, meaning another browser holds the port: use `open(cdp_port=9333)` or set `WECHAT_CDP_PORT`; the other tools then reuse the port automatically. Since 0.9.19 `open` fails fast instead of reporting that browser's errors as startup errors |
| Automator port 9420 unreachable / `start` returns `verified=false` | Since 0.9.19 actions run `start` once and retry on their own; `start` waits up to 45s for readiness (`ready_timeout`). If it still fails, check `project_window_open` in `status`: if the window was closed, run `start` again rather than `open` (which restarts the IDE) |
| Garbled Chinese or `UnicodeDecodeError` on Windows | Add `"PYTHONIOENCODING": "utf-8"` to `env` |
| Old version still runs after installing | `pip uninstall wechat-devtools-mcp`; for `uvx` setups run `uvx --refresh wechat-devtools-mcp --version`; `mcp_version` from `status` is the final word |
| Odd tool behaviour on IDE 2.x | Registration name clashes with the official `wechat-devtools`; use `wechat-devtools-mcp` |

---

## 📋 Changelog

| Version | Date | Summary |
|---------|------|---------|
| 0.9.19 | 2026-10-26 | `start` waits for automator readiness with a deadline, fixing false "handshake incomplete" failures; CDP port occupant check and session stickiness (`WECHAT_CDP_PORT`); automatic automator recovery; `status` reports project window and skill version |
| 0.9.18 | 2026-09-04 | Windows 2.x verified on a real machine: `User Data` state dir, readiness, `quit` waits for exit, noise filters; new smoke script |
| 0.9.17 | 2026-09-03 | DevTools 2.x Stable support; `fn_source` for evaluate; ~4x faster `open`; Windows dual-runtime detection |
| 0.9.16 | 2026-08-27 | Long-page screenshot overhaul; source code opened |
| 0.9.15 | 2026-08-20 | DevTools 2.x (Electron) support; CDP capture returning 0 entries since 0.9.0 fixed |
| 0.9.14 | 2026-08-20 | Unified `wechat_file` path resolution; `cdp_port` forwarding fix |
| 0.9.13 | 2026-08-18 | `--version` early exit; documentation fixes |

Full per-version notes: [CHANGELOG_EN.md](./CHANGELOG_EN.md).

---

## References

- [WeChat DevTools CLI](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html) · [Mini Program Automation SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)
- License: MIT
