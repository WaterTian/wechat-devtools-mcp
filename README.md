# 微信开发者工具 MCP Server (v0.9.17)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![English](https://img.shields.io/badge/lang-English-blue.svg)](./README_EN.md)

> 把微信开发者工具封装为 [MCP](https://modelcontextprotocol.io/) 服务，让编辑器里的 AI 直接完成小程序的**编译、预览、调试、自动化测试**闭环。Windows / macOS，已上架官方 MCP Registry。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

> [!IMPORTANT]
> 「瘦 MCP + 胖 Skill」：MCP Server 只提供 7 个聚合工具，操作流程与最佳实践都在配套的 [wechat-devtools Skill](#step-5--安装-skill必须) 里。**两者必须一起装**。

---

## 🤝 与官方能力的关系

微信开发者工具 **2.x 自 2026-08-18 起为官方 Stable**（1.06 已下架），IDE 内建 MCP Server（47 个原子工具）。两者互补，不是替代：

| 场景 | 用谁 |
|------|------|
| 打开项目 / 编译 / 预览 / 上传 / 点击输入 / 云开发 | 2.x 优先官方内建 MCP（`wechat_ide(action='status')` 的 `official_mcp.available` 为 `true` 即可用） |
| **长图拼接截图**（固定头尾识别，拍不全如实上报） | 本项目。官方只截视口并压到长边 1280 JPEG |
| **CDP 结构化日志**（回放采集前的历史、按页面归类、去噪） | 本项目。官方只读缓存 |
| **任务级 SOP**（一句话跑完巡检 / 异常排查 / 跨页面校验） | 本项目 Skill |
| 存量 1.06.x（NW.js） | 本项目继续兼容；官方内建 MCP 仅 2.x 有 |

> ⚠ 官方 IDE 把自家 bridge 注册为 `wechat-devtools`。本文示例统一用 **`wechat-devtools-mcp`** 避免撞名；旧名配置仍可用，只在同一 agent 同时接入两者时才需区分。

---

## 🚀 快速开始

### Step 1 — 安装 MCP Server

```bash
pip install uv                                  # 如已装可跳过
uv tool install wechat-devtools-mcp --force
wechat-devtools-mcp --version                   # 确认实际运行版本
```

> [!WARNING]
> 曾用 `pip install` 装过旧版的，先 `pip uninstall wechat-devtools-mcp`，否则旧路径优先于 uv。
> ≤0.9.10 与 mcp SDK ≥2.0 不兼容（报 `ModuleNotFoundError: mcp.server.fastmcp`），请升到 ≥0.9.11。

升级前先停掉编辑器里正在跑的 MCP 进程，再 `uv tool upgrade wechat-devtools-mcp`。

### Step 2 — 开启开发者工具服务端口

`开发者工具` → `设置` → `安全设置` → `服务端口` → `开启`。不开则所有操作报 `CLI_TIMEOUT`。

### Step 3 — 准备两个绝对路径

| 路径 | Windows | macOS |
|------|---------|-------|
| 开发者工具 CLI | `C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat` | `/Applications/wechatwebdevtools.app/Contents/MacOS/cli` |
| 小程序项目根目录 | `D:\MyProjects\mini-app` | `/Users/<you>/Projects/mini-app` |

JSON 里 Windows 路径的 `\` 要写成 `\\`；macOS 的 `/` 不用转义。

### Step 4 — 编辑器配置

标准配置（Claude Desktop / Antigravity / Kiro / Trae / Claude Code `.mcp.json` 通用）：

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

| 编辑器 | 配置位置 | 差异 |
|--------|----------|------|
| Claude Desktop / Antigravity | `claude_desktop_config.json` / `mcp_config.json` | 无 |
| Claude Code（项目级） | 仓库根目录 `.mcp.json` | macOS 下 `command` 用绝对路径 `/opt/homebrew/bin/uvx`，并在 `env` 加 `"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"` 与 `"NODE_PATH": "/opt/homebrew/bin/node"`（GUI 子进程不带 Homebrew PATH） |
| Kiro | `~/.kiro/settings/mcp.json` | 可加 `"autoApprove": ["wechat_ide","wechat_build","wechat_automator","wechat_inspector","wechat_screenshot","wechat_navigate","wechat_file"]` |
| Trae ≥1.3 | AI 面板 → 设置 → MCP → 手动配置；或 `%APPDATA%\Trae\User\globalStorage\mcp.json` / `~/Library/Application Support/Trae/User/globalStorage/mcp.json` | 聊天须选 **Builder with MCP** 智能体；macOS 同 Claude Code 的绝对路径写法 |
| Cursor / VS Code | MCP 面板新增 server | Name `wechat-devtools-mcp`，Command `uvx wechat-devtools-mcp`，环境变量同上 |
| OpenAI Codex | `~/.codex/config.toml` | TOML，见下 |

```toml
[mcp_servers.wechat-devtools-mcp]
command = "uvx"
args = ["wechat-devtools-mcp"]

[mcp_servers.wechat-devtools-mcp.env]
WECHAT_DEVTOOLS_CLI = "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat"
WECHAT_PROJECT_PATH = "D:\\Your\\Project\\Path"
```

### Step 5 — 安装 Skill（必须）

```bash
npx -y skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
```

不走 `npx skills` 的客户端（如 Trae）：把仓库的 `.agents/skills/wechat-devtools/` 整个复制到小程序项目的 `.agents/skills/` 下即可。Skill 含 9 条 SOP、7 工具全 action 速查、CDP 渐进排查策略与故障手册，详见 [SKILL.md](./.agents/skills/wechat-devtools/SKILL.md)。

---

## 🛠️ 工具箱

| 工具 | 用途 | action / 关键参数 |
|------|------|------------------|
| `wechat_ide` | IDE 生命周期与环境诊断 | `open` `login` `is_login` `close` `quit` `status` |
| `wechat_build` | 构建与发布 | `compile` `preview` `upload` `build_npm` `cache_clean` |
| `wechat_automator` | 自动化交互与运行时查询 | `start` `tap` `input` `element_info` `set_data` `call_method` `call_wx` `mock_wx` `evaluate` `page_stack` `page_data` `system_info` `storage` |
| `wechat_inspector` | 运行时日志采集 | `console` `cdp` |
| `wechat_screenshot` | 长图拼接截图 | `full_page` `page_path` `scroll_top` |
| `wechat_navigate` | 跳转并采集 CDP 日志 | `page_path` |
| `wechat_file` | 项目文件读取 | `project_info` `list_pages` `read_page` `read_file` |

完整参数见 [MCP_DOC.md](./MCP_DOC.md)。云函数与云数据库请用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)。

---

## 💡 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `WECHAT_DEVTOOLS_CLI` | 开发者工具 CLI 路径（**必填**） | — |
| `WECHAT_PROJECT_PATH` | 默认项目根目录（**必填**） | — |
| `WECHAT_CLI_TIMEOUT` | CLI 超时秒数 | `30` |
| `NODE_PATH` | Node.js 可执行文件 | `node` |

---

## ❓ 常见问题

| 症状 | 处理 |
|------|------|
| 一直报 `CLI_TIMEOUT` | 服务端口没开，见 Step 2；`wechat_ide(action='status')` 的 `service_port_enabled` 可自查 |
| CDP 采集失败 / 采到的全是 Chrome | 9222 被占用。`open(cdp_port=9223)`，且 `inspector` / `navigate` / `build` 用同一个 `cdp_port` |
| Windows 中文乱码或 `UnicodeDecodeError` | `env` 加 `"PYTHONIOENCODING": "utf-8"` |
| 装了新版仍跑旧版 | `pip uninstall wechat-devtools-mcp`，再用 `wechat-devtools-mcp --version` 确认 |
| IDE 2.x 下工具行为异常 | 注册名与官方 `wechat-devtools` 撞车，改用 `wechat-devtools-mcp` |

---

## 📋 版本历史

| 版本 | 日期 | 摘要 |
|------|------|------|
| 0.9.17 | 2026-09-03 | 适配开发者工具 2.x Stable；evaluate 新增 `fn_source`；`open` 提速约 4 倍；Windows 1.x/2.x 双轨判定 |
| 0.9.16 | 2026-08-27 | 长页面截图全面修复；源码开源 |
| 0.9.15 | 2026-08-20 | 适配开发者工具 2.x（Electron）；修复 CDP 采集自 0.9.0 起恒为 0 条 |
| 0.9.14 | 2026-08-20 | `wechat_file` 路径口径统一；`cdp_port` 透传修复 |
| 0.9.13 | 2026-08-18 | `--version` 早退；文档核对修复 |
| 0.9.12 | 2026-08-18 | 握手返回包版本；依赖上界 `mcp<3` |

完整逐版本说明见 [CHANGELOG.md](./CHANGELOG.md)。

---

## 参考

- [微信开发者工具 CLI](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html) · [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)
- 许可证：MIT
