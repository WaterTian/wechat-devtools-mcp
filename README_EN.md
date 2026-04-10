# WeChat DevTools MCP Server (v0.9.0)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![中文文档](https://img.shields.io/badge/lang-中文文档-red.svg)](./README.md)

> Wraps the WeChat DevTools CLI as an [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server, enabling AI editors to directly invoke WeChat CLI commands for a complete Mini Program **development, testing, debugging, and automation** workflow.

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

> [!IMPORTANT]
> This project uses a **"Lean MCP + Rich Skill"** architecture: **the MCP Server provides 8 aggregated APIs, while the companion [wechat-devtools Skill](#step-5--install-skill-required) provides SOP workflows, parameter references, and best practices. Both must be used together** — without the Skill, the AI can only call raw APIs and cannot execute standardized testing and debugging workflows.

**Published to the official [MCP Registry](https://modelcontextprotocol.io/)** with cross-platform (Windows / macOS) one-click installation.

---

> **🌐 [中文文档 →](./README.md)**

---

## 🚀 Installation & Quick Start

### Step 1 — Install MCP Server

We recommend [uv](https://github.com/astral-sh/uv), which automatically handles Python dependencies in an isolated environment.

```bash
pip install uv                                  # Install uv (skip if already installed)
uv tool install wechat-devtools-mcp --force     # One-click install to global isolated env
```

> [!TIP]
> - Check installed version: `uv tool list`
> - Upgrade: if your editor is running the MCP service, stop the process first:
>   ```powershell
>   # Windows PowerShell
>   Get-Process | Where-Object { $_.ProcessName -like "*wechat-devtools*" } | Stop-Process -Force
>   uv tool upgrade wechat-devtools-mcp
>   ```

### Step 2 — Enable DevTools Service Port

> [!WARNING]
> This must be enabled manually, otherwise the AI cannot send any commands.

**Path**: `DevTools` → `Settings` → `Security` → `Service Port` → `Enable`

### Step 3 — Confirm Required Paths

Prepare the following two absolute paths for the editor configuration:

| Path | Example |
|------|---------|
| WeChat DevTools CLI | `C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat` |
| Mini Program project root | `D:\MyProjects\mini-app` |

### Step 4 — Editor Configuration

<details>
<summary><b>Claude Desktop / Antigravity</b></summary>

Edit `claude_desktop_config.json` or `mcp_config.json` (Antigravity):

```json
{
  "mcpServers": {
    "wechat-devtools": {
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
</details>

<details>
<summary><b>Kiro</b></summary>

Edit `~/.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "wechat-devtools": {
      "command": "uvx",
      "args": ["wechat-devtools-mcp"],
      "env": {
        "WECHAT_DEVTOOLS_CLI": "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat",
        "WECHAT_PROJECT_PATH": "D:\\Your\\Project\\Path",
        "PYTHONIOENCODING": "utf-8"
      },
      "autoApprove": [
        "wechat_ide", "wechat_build", "wechat_automator", "wechat_inspector",
        "wechat_screenshot", "wechat_navigate", "wechat_file", "wechat_cloud"
      ]
    }
  }
}
```
</details>

<details>
<summary><b>OpenAI Codex</b></summary>

Edit `~/.codex/config.toml` (global) or `.codex/config.toml` (project-level):

```toml
[mcp_servers.wechat-devtools]
command = "uvx"
args = ["wechat-devtools-mcp"]

[mcp_servers.wechat-devtools.env]
WECHAT_DEVTOOLS_CLI = "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat"
WECHAT_PROJECT_PATH = "D:\\Your\\Project\\Path"
```

Or add via CLI:

```bash
codex mcp add wechat-devtools \
  --env WECHAT_DEVTOOLS_CLI="C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat" \
  --env WECHAT_PROJECT_PATH="D:\\Your\\Project\\Path" \
  -- uvx wechat-devtools-mcp
```
</details>

<details>
<summary><b>Cursor / VS Code (MCP Plugin)</b></summary>

Add a new Server in the MCP console:

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: add `WECHAT_DEVTOOLS_CLI` and `WECHAT_PROJECT_PATH` as above

> On Windows, backslashes in paths must be escaped (`\\`).
</details>

### Step 5 — Install Skill (Required)

> [!IMPORTANT]
> **This MCP must be used with the wechat-devtools Skill.** The Skill contains all SOP workflows, parameter references, and troubleshooting guides the AI needs to operate Mini Programs. Without it, the AI can only call raw APIs and cannot execute standardized workflows.

**Option 1: Via GitHub repository reference (recommended)**

```bash
npx skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
```

**Option 2: Manual copy**

Copy the `.agents/skills/wechat-devtools/` directory to your project or global skills directory:

```
.agents/skills/
└── wechat-devtools/
    ├── SKILL.md                    # Main instruction file (SOPs + capability mapping + red lines)
    └── references/
        └── tool_reference.md       # Complete parameter reference for all 8 aggregated APIs
```

---

## 🛠️ Toolbox Overview

The MCP Server provides **8 aggregated tools** covering the full Mini Program lifecycle:

| Tool | Function | Supported Actions |
|------|----------|-------------------|
| `wechat_ide` | IDE lifecycle management | `open` `login` `is_login` `close` `quit` `status` |
| `wechat_build` | Build & publish | `compile` `preview` `upload` `build_npm` `cache_clean` |
| `wechat_automator` | Automation & interaction | `start` `tap` `input` `element_info` `set_data` `call_method` `call_wx` `mock_wx` `evaluate` `page_stack` `page_data` `system_info` `storage` |
| `wechat_inspector` | Runtime log collection | `console` `cdp` |
| `wechat_screenshot` | Screenshot (long-page stitching) | — |
| `wechat_navigate` | Navigate & capture CDP logs | — |
| `wechat_file` | Project file reading | `project_info` `list_pages` `read_page` `read_file` |
| `wechat_cloud` | Cloud functions & database | `env_list` `func_list` `func_info` `func_deploy` `func_download` `db_collection_add` `db_collection_count` |

> For complete parameter documentation, see **[MCP_DOC.md](./MCP_DOC.md)**

---

## 🧠 Skill Details

The Skill enables AI to automatically match and execute standardized workflows from natural language instructions:

| What you say | Workflow executed |
|-------------|-------------------|
| "Check all pages for errors" | SOP D — Full page inspection |
| "Click the login button, take a screenshot" | SOP B — UI debugging |
| "Page is blank, help me troubleshoot" | SOP C — Error investigation |
| "Mock the payment API, test the payment flow" | SOP E — Mock integration testing |
| "Test the detail page, what are the params?" | SOP G — Sub-page testing |
| "Deploy cloud function and verify it works" | SOP H — Cloud function deployment |
| "Compare points across all pages" | SOP I — Cross-page data validation |

### What's Included

- **10 SOP workflows** — Initialization, UI debugging, error investigation, full page inspection, mock integration testing, network debugging & UI adaptation, sub-page testing, cloud function deployment, cross-page data validation, parallel data comparison
- **Capability mapping** — 8 aggregated tools × all actions quick reference
- **CDP progressive debugging** — concise → full two-stage strategy to control token usage
- **Complete parameter reference** — Required/optional params, return examples, common templates
- **Troubleshooting guide** — Common error codes and fixes

> For installation, see [Step 5 — Install Skill](#step-5--install-skill-required)

---

## 💡 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `WECHAT_DEVTOOLS_CLI` | WeChat DevTools CLI path | — | **Yes** |
| `WECHAT_PROJECT_PATH` | Default Mini Program project absolute path | — | **Yes** |
| `WECHAT_CLI_TIMEOUT` | CLI command timeout (seconds) | `30` | No |
| `NODE_PATH` | Node.js executable path | `node` | No |

---

## ❓ FAQ

<details>
<summary><b>Why does the AI keep reporting <code>CLI_TIMEOUT</code>?</b></summary>

**Most common cause**: The DevTools "Service Port" is not enabled.
Go to `Settings` → `Security` → `Service Port` and turn it on. No IDE restart needed — the AI will reconnect immediately.
</details>

<details>
<summary><b><code>wechat_inspector</code> returns "CDP collection failed"</b></summary>

If you opened DevTools manually, it may not be listening on the debug port. **Close DevTools** and let the AI run `wechat_ide(action='open', cdp_enabled=True)` to start in debug mode.
</details>

<details>
<summary><b><code>uv tool upgrade</code> says file is in use?</b></summary>

The MCP service is still running in your editor. See the upgrade tip under [Step 1](#step-1--install-mcp-server) — stop the process first, then upgrade.
</details>

<details>
<summary><b>AI can't find the WeChat CLI path?</b></summary>

Make sure `WECHAT_DEVTOOLS_CLI` in your editor config contains an absolute path. On Windows, use double backslashes (e.g., `C:\\...\\cli.bat`).
</details>

---

## 📋 Changelog

| Version | Description |
|---------|-------------|
| **0.9.0** | **Persistent Node daemon architecture**: single long-running daemon process with NDJSON protocol, WS connections cached by port; single daemon.bundle.js replaces 8 individual bundles; tool call latency reduced from 500ms+ to ~3ms; zero disconnections after compile with automatic reconnection |
| **0.8.0** | Auto-reconnect automator after compile; navigate auto-detects TabBar pages using switchTab; screenshot adds full\_page/scroll\_top/page\_path params for viewport mode; page\_data adds expected\_path polling to prevent stale data; long screenshot dynamic step adjustment fixes content gaps; node\_bridge unified connection retry + 500ms call interval; start port verification increased to 20 attempts |
| **0.7.0** | Fix navigate scoping bug (currentPageTimeout); evaluate supports declaration statements (const/let/var fallback); call_method returns current page path; automator start uses port polling instead of blind sleep; SKILL.md adds efficiency principles, recovery tiers, page navigation methods, 6 new fault entries |
| **0.6.0** | Navigate supports query params (reLaunch timeout fallback); CDP startup noise filtering (console.assert/\_\_route\_\_/ide:// noise reduction + WXML error protection); compile returns tri-state + automator invalidation hint; navigate currentPage polling retry; configurable timeout |
| **0.5.1** | `wechat_ide(action='open')` adds CDP startup health check: auto-captures 5s of CDP logs to detect fatal startup errors, returns failure to stop subsequent operations |
| **0.5.0** | Skill SOP overhaul: added SOP I/J; AppID check & path validation; CDP noise filtering; screenshot stitching fuzzy matching fix |
| **0.4.1** | Long-page screenshot rewrite: fixed region detection, DPR adaptation, dynamic overlap calculation |
| **0.4.0** | CDP log enhancement, cloud function auto-verification, navigate smart diagnostics, new SOP G/H |
| **0.3.0** | **Major refactor**: 44 tools consolidated into 8 APIs; CDP logs v2; SKILL.md knowledge base |

<details>
<summary>Earlier versions</summary>

| Version | Description |
|---------|-------------|
| 0.2.6 | Added OpenAI Codex configuration to README |
| 0.2.5 | Added Kiro editor configuration |
| 0.2.4 | Screenshot stitching fix: `sharp` → `jimp` |
| 0.2.3 | Package optimization: exclude `scripts/` source, keep only `dist/` bundles |
| 0.2.2 | Node.js scripts switched to bundle-only mode |
| 0.2.1 | Version update & documentation improvements |
| 0.2.0 | Navigate switched to CDP high-quality log collection |
| 0.1.9 | Fix UTF-8 encoding issues |
| 0.1.8 | Fix Windows Chinese path UnicodeDecodeError |
| 0.1.7 | Added core/full tool presets; added MCP_DOC.md |
| 0.1.6 | `wechat_open(cdp_enabled=true)` auto-kills existing process |
| 0.1.5 | Fix Windows stdio blocking |
| 0.1.4 | Added CDP logs, screenshots, automation features |
| 0.1.3 | Initial release |
</details>

---

## References

- [WeChat DevTools CLI Documentation](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [Mini Program Automation SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## License

MIT
