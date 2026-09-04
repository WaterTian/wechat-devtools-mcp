# WeChat DevTools MCP Server (v0.9.17)

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

WeChat DevTools **2.x has been the official Stable channel since 2026-08-18** (1.06 is no longer offered). The IDE ships a built-in MCP server (47 atomic tools). The two are complementary, not substitutes:

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

### Step 1 — Install the MCP Server

```bash
pip install uv                                  # skip if already installed
uv tool install wechat-devtools-mcp --force
wechat-devtools-mcp --version                   # confirm the running version
```

> [!WARNING]
> If an older version was installed with `pip install`, run `pip uninstall wechat-devtools-mcp` first; the pip path shadows uv's.
> ≤0.9.10 is incompatible with mcp SDK ≥2.0 (`ModuleNotFoundError: mcp.server.fastmcp`); upgrade to ≥0.9.11.

Stop the MCP process running inside your editor before `uv tool upgrade wechat-devtools-mcp`.

### Step 2 — Enable the DevTools Service Port

`DevTools` → `Settings` → `Security` → `Service Port` → `Enable`. Without it every call fails with `CLI_TIMEOUT`.

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

| Editor | Where | Differences |
|--------|-------|-------------|
| Claude Desktop / Antigravity | `claude_desktop_config.json` / `mcp_config.json` | none |
| Claude Code (per project) | `.mcp.json` in the repo root | On macOS use the absolute `command` `/opt/homebrew/bin/uvx` and add `"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"` plus `"NODE_PATH": "/opt/homebrew/bin/node"` to `env` (GUI child processes lack the Homebrew PATH) |
| Kiro | `~/.kiro/settings/mcp.json` | optional `"autoApprove": ["wechat_ide","wechat_build","wechat_automator","wechat_inspector","wechat_screenshot","wechat_navigate","wechat_file"]` |
| Trae ≥1.3 | AI panel → Settings → MCP → Manual; or `%APPDATA%\Trae\User\globalStorage\mcp.json` / `~/Library/Application Support/Trae/User/globalStorage/mcp.json` | Chat must use the **Builder with MCP** agent; macOS uses the same absolute paths as Claude Code |
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

Full parameters: [MCP_DOC.md](./MCP_DOC.md). Cloud functions and databases: use [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit).

---

## 💡 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WECHAT_DEVTOOLS_CLI` | DevTools CLI path (**required**) | — |
| `WECHAT_PROJECT_PATH` | Default project root (**required**) | — |
| `WECHAT_CLI_TIMEOUT` | CLI timeout in seconds | `30` |
| `NODE_PATH` | Node.js executable | `node` |

---

## ❓ FAQ

| Symptom | Fix |
|---------|-----|
| Constant `CLI_TIMEOUT` | Service port is off, see Step 2; `wechat_ide(action='status')` exposes `service_port_enabled` |
| CDP capture fails / only Chrome shows up | Port 9222 is taken. Use `open(cdp_port=9223)` and pass the same `cdp_port` to `inspector` / `navigate` / `build` |
| Garbled Chinese or `UnicodeDecodeError` on Windows | Add `"PYTHONIOENCODING": "utf-8"` to `env` |
| Old version still runs after installing | `pip uninstall wechat-devtools-mcp`, then check `wechat-devtools-mcp --version` |
| Odd tool behaviour on IDE 2.x | Registration name clashes with the official `wechat-devtools`; use `wechat-devtools-mcp` |

---

## 📋 Changelog

| Version | Date | Summary |
|---------|------|---------|
| 0.9.17 | 2026-09-03 | DevTools 2.x Stable support; `fn_source` for evaluate; ~4x faster `open`; Windows dual-runtime detection |
| 0.9.16 | 2026-08-27 | Long-page screenshot overhaul; source code opened |
| 0.9.15 | 2026-08-20 | DevTools 2.x (Electron) support; CDP capture returning 0 entries since 0.9.0 fixed |
| 0.9.14 | 2026-08-20 | Unified `wechat_file` path resolution; `cdp_port` forwarding fix |
| 0.9.13 | 2026-08-18 | `--version` early exit; documentation fixes |
| 0.9.12 | 2026-08-18 | Package version in handshake; dependency upper bound `mcp<3` |

Full per-version notes: [CHANGELOG_EN.md](./CHANGELOG_EN.md).

---

## References

- [WeChat DevTools CLI](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html) · [Mini Program Automation SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)
- License: MIT
