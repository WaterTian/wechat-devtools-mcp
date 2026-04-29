# 微信开发者工具 MCP Server (v0.9.6)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![English](https://img.shields.io/badge/lang-English-blue.svg)](./README_EN.md)

> 将微信开发者工具 CLI 封装为 [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) 服务，使编辑器中的 AI 能够直接调用微信 CLI 命令，实现小程序**开发、测试、调试、自动化**全流程闭环。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

> [!IMPORTANT]
> 本项目采用「**瘦 MCP + 胖 Skill**」架构：**MCP Server 提供 8 个聚合 API，配套的 [wechat-devtools Skill](#-安装-skill必须) 提供 SOP 流程、参数速查和最佳实践。两者必须配合使用**，缺少 Skill 时 AI 将无法按正确流程操作小程序。

**已发布至官方 [MCP Registry](https://modelcontextprotocol.io/)**，支持跨平台（Windows / macOS）一键安装。

---

> **🌐 [English Documentation →](./README_EN.md)**

---

## 🚀 安装与快速开始

### Step 1 — 安装 MCP Server

推荐使用 [uv](https://github.com/astral-sh/uv)，它能自动处理 Python 依赖并提供隔离的执行环境。

```bash
pip install uv                                  # 安装 uv（如已安装可跳过）
uv tool install wechat-devtools-mcp --force     # 一键安装到全局隔离环境
```

> [!WARNING]
> 如果之前通过 `pip install` 安装过旧版本，请先卸载以避免版本冲突：
> ```bash
> pip uninstall wechat-devtools-mcp
> ```
> `pip install` 的路径（如 `Python313/Scripts/`）可能优先于 `uv tool install` 的路径（`~/.local/bin/`），导致实际运行旧版本。可通过 `wechat_ide(action='status')` 返回的 `mcp_version` 字段确认当前版本。

> [!TIP]
> - 查看已安装版本：
>   ```bash
>   uv tool list | grep wechat    # 离线确认已安装版本
>   ```
> - 升级工具：如果编辑器正在运行 MCP 服务，需先终止进程再升级：
>   ```bash
>   # Bash / CMD
>   taskkill /F /IM "wechat-devtools-mcp*" 2>/dev/null; uv tool upgrade wechat-devtools-mcp
>   ```
>   ```powershell
>   # Windows PowerShell
>   Get-Process | Where-Object { $_.ProcessName -like "*wechat-devtools*" } | Stop-Process -Force
>   uv tool upgrade wechat-devtools-mcp
>   ```
> - Agent 一键升级：
>   ```bash
>   taskkill /F /IM "wechat-devtools-mcp*" 2>/dev/null; uv tool upgrade wechat-devtools-mcp && npx -y skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
>   ```

### Step 2 — 开启开发者工具服务端口

> [!WARNING]
> 必须手动开启，否则 AI 将无法下发任何指令。

**操作路径**：`开发者工具` → `设置` → `安全设置` → `服务端口` → `开启`

> 💡 可通过 `wechat_ide(action='status')` 验证端口是否已开启——如果返回连接失败，说明服务端口尚未启用。

### Step 3 — 确认必要路径

请提前获取以下两个绝对路径，稍后需填入编辑器配置：

| 路径 | Windows 示例 | macOS 示例 |
|------|-------------|-----------|
| 微信开发者工具 CLI | `C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat` | `/Applications/wechatwebdevtools.app/Contents/MacOS/cli` |
| 小程序项目根目录 | `D:\MyProjects\mini-app` | `/Users/<you>/Projects/mini-app` |

> macOS 用户：JSON 配置中无需转义斜杠（`/` 直接写）；Windows 用户需把 `\` 写成 `\\`。

### Step 4 — 编辑器配置

<details>
<summary><b>Claude Desktop / Antigravity</b></summary>

修改 `claude_desktop_config.json` 或 `mcp_config.json`（Antigravity）：

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

编辑 `~/.kiro/settings/mcp.json`：

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
        "wechat_screenshot", "wechat_navigate", "wechat_file"
      ]
    }
  }
}
```
</details>

<details>
<summary><b>OpenAI Codex</b></summary>

编辑 `~/.codex/config.toml`（全局）或 `.codex/config.toml`（项目级）：

```toml
[mcp_servers.wechat-devtools]
command = "uvx"
args = ["wechat-devtools-mcp"]

[mcp_servers.wechat-devtools.env]
WECHAT_DEVTOOLS_CLI = "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat"
WECHAT_PROJECT_PATH = "D:\\Your\\Project\\Path"
```

也可以通过 CLI 快速添加：

```bash
codex mcp add wechat-devtools \
  --env WECHAT_DEVTOOLS_CLI="C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat" \
  --env WECHAT_PROJECT_PATH="D:\\Your\\Project\\Path" \
  -- uvx wechat-devtools-mcp
```
</details>

<details>
<summary><b>Cursor / VS Code (MCP Plugin)</b></summary>

在 MCP 控制台中添加新 Server：

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: 同上添加 `WECHAT_DEVTOOLS_CLI` 和 `WECHAT_PROJECT_PATH`

> Windows 下路径中的反斜杠需要转义（`\\`）。
</details>

### Step 5 — 安装 Skill（必须）

> [!IMPORTANT]
> **本 MCP 必须配合 wechat-devtools Skill 使用。** Skill 包含 AI 操作小程序所需的全部 SOP 流程、参数速查和故障排查指南。未安装 Skill 时，AI 只能调用裸 API，无法自动执行标准化测试和调试流程。

**方式一：通过 GitHub 仓库引用（推荐）**

```bash
npx -y skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
```

**方式二：手动复制**

将 `.agents/skills/wechat-devtools/` 目录复制到你的项目或全局 skills 目录：

```
.agents/skills/
└── wechat-devtools/
    ├── SKILL.md                    # 主指令文件（SOP + 能力映射 + 红线规则）
    └── references/
        └── tool_reference.md       # 7 个聚合 API 完整参数参考
```

---

## 🛠️ 工具箱概要

MCP Server 提供 **7 个聚合工具**，覆盖小程序全生命周期：

| 工具 | 功能 | 支持的 action |
|------|------|--------------|
| `wechat_ide` | IDE 生命周期管理 | `open` `login` `is_login` `close` `quit` `status` |
| `wechat_build` | 构建与发布 | `compile` `preview` `upload` `build_npm` `cache_clean` |
| `wechat_automator` | 自动化交互 | `start` `tap` `input` `element_info` `set_data` `call_method` `call_wx` `mock_wx` `evaluate` `page_stack` `page_data` `system_info` `storage` |
| `wechat_inspector` | 运行时日志采集 | `console` `cdp` |
| `wechat_screenshot` | 界面截图（长图拼接） | — |
| `wechat_navigate` | 跳转页面并采集 CDP 日志 | — |
| `wechat_file` | 项目文件读取 | `project_info` `list_pages` `read_page` `read_file` |

> 云函数与云数据库管理请使用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)（`manageFunctions` / `readNoSqlDatabaseContent` 等），功能更完整且无 IDE 依赖。`wechat_cloud` 自 v0.9.5 起已禁用。
>
> 完整工具参数说明请参阅 **[MCP_DOC.md](./MCP_DOC.md)**

---

## 🧠 Skill 内容详情

Skill 让 AI 在收到自然语言指令后，自动匹配并执行标准化操作流程：

| 你说的话 | AI 执行的流程 |
|---------|--------------|
| "帮我检查所有页面有没有报错" | SOP D — 全页面巡检 |
| "点击登录按钮，截图看看效果" | SOP B — UI 调试 |
| "页面白屏了，帮我排查" | SOP C — 异常排查 |
| "Mock 支付接口，测试支付流程" | SOP E — Mock 集成测试 |
| "测试详情页，参数名是什么" | SOP G — 子页面测试 |
| "对比各页面积分是否一致" | SOP I — 跨页面数据校验 |

### Skill 包含

- **9 个 SOP 流程** — 初始化、UI 调试、异常排查、全页面巡检、Mock 集成测试、网络调试与 UI 适配、子页面测试、跨页面数据校验、并行数据比对
- **能力映射字典** — 7 个聚合工具 × 全部 action 的快速索引
- **CDP 渐进排查策略** — concise → full 两阶段，控制 Token 消耗
- **完整参数参考** — 每个 action 的必填/可选参数、返回示例、常用模板
- **故障排查手册** — 常见错误码与修复方式

> 安装方式见 [Step 5 — 安装 Skill](#step-5--安装-skill必须)

---

## 💡 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | 微信开发者工具 CLI 路径 | — | **是** |
| `WECHAT_PROJECT_PATH` | 默认小程序项目绝对路径 | — | **是** |
| `WECHAT_CLI_TIMEOUT` | CLI 命令超时时间（秒） | `30` | 否 |
| `NODE_PATH` | Node.js 执行文件路径 | `node` | 否 |

---

## ❓ 常见问题

<details>
<summary><b>为什么 AI 总是报 <code>CLI_TIMEOUT</code> 错误？</b></summary>

**最常见原因**：微信开发者工具的"服务端口"未开启。
进入 `设置` → `安全` → `服务端口`，将其打开。开启后无需重启 IDE，AI 即可恢复连接。
</details>

<details>
<summary><b><code>wechat_inspector</code> 返回"CDP 采集失败"</b></summary>

如果手动打开了开发者工具，它可能未监听调试端口。**请关闭开发者工具**，让 AI 执行 `wechat_ide(action='open', cdp_enabled=True)` 以调试模式启动。
</details>

<details>
<summary><b><code>uv tool upgrade</code> 提示文件被占用？</b></summary>

编辑器中的 MCP 服务仍在运行。参见 [Step 1](#step-1--安装-mcp-server) 下方的升级提示——需先终止进程再升级。
</details>

<details>
<summary><b><code>uv tool install</code> 后仍运行旧版本？</b></summary>

可能是 `pip install` 安装的旧版本优先级更高。运行 `pip uninstall wechat-devtools-mcp` 移除旧版本，然后通过 `wechat_ide(action='status')` 确认 `mcp_version` 字段为最新版本。
</details>

<details>
<summary><b>AI 无法找到微信 CLI 路径？</b></summary>

在编辑器配置的 `env` 中确保 `WECHAT_DEVTOOLS_CLI` 填入了绝对路径：
- **Windows**: 使用双反斜杠（如 `C:\\...\\cli.bat`）
- **macOS**: 标准路径 `/Applications/wechatwebdevtools.app/Contents/MacOS/cli`，斜杠无需转义
</details>

<details>
<summary><b>macOS 上 Node.js 检测失败？</b></summary>

GUI 客户端（如 Claude Desktop）启动 MCP 时 `PATH` 可能不包含 `/opt/homebrew/bin`。MCP v0.9.6 起会自动尝试 Homebrew 标准路径；若仍失败，可在 `env` 中显式设置：
```json
"NODE_PATH": "/opt/homebrew/bin/node"
```
</details>

---

## 📋 版本历史

| 版本 | 说明 |
|------|------|
| **0.9.6** | **macOS 适配**：`cdp_enabled=true` 模式跨平台启动（NW.js 主程序 `wechatdevtools` + `package.nw` 入口 + `pkill` 清理）；默认 CLI 路径按平台返回；Node.js 检测补 Homebrew/nvm 候选路径；README 增加 macOS 路径示例 |
| **0.9.5** | **修复 compile 健康检查永久失败的潜伏 bug**（ui_debug.js 无 `page_stack` action，v0.9.0 以来 `automator_verified` 一直误报 false）；compile 对 `EACCES`/`EADDRINUSE`/`#initialize-error` 等致命 pattern 降级为 fail，杜绝「假成功发布旧 bundle」；preview 自动 resolve 相对路径 + mtime 新鲜度检测；`wechat_automator(action='start')` 升级为 TCP+WS 双重验证 + `retry_after_ms` 精确等待；compile 前检测 `miniprogram_npm` 过期发 warning；inspector 短 duration 捕获异常时发 warning；`wechat_cloud` 工具已禁用（改用 CloudBase MCP） |
| **0.9.4** | 修复 switchTab 跳转不生效（改用 `miniProgram.switchTab()` 替代 `callWxMethod`）；compile 后重连稳定性（去冗余进程 + 3s 延迟 + WS 健康检查）；README 5 项 agent 友好性改进 |
| **0.9.3** | status 新增 `mcp_version` 字段用于版本确认；启动时打印版本号到 stderr；README 增加 pip/uv 版本冲突排查指引 |
| **0.9.2** | **修复 compile 后 navigate 超时**：daemon 连接健康检查增加 3s 超时保护；compile 后自动 invalidate 旧缓存连接再重连；navigate currentPage 轮询每次调用增加 2s 独立超时；区分 HEALTH\_CHECK\_TIMEOUT 和 CONNECTION\_ERROR 错误码 |
| **0.9.1** | 修复 cdp\_enabled=true 时 AttributeError 崩溃；新增 WXML 运行时错误采集（compile 后 CDP 自动捕获 template not found 等警告） |
| **0.9.0** | **持久化 Node daemon 架构**：单 daemon 进程常驻，NDJSON 协议通信，WS 连接按端口复用；单个 daemon.bundle.js 替代 8 个独立 bundle；工具调用延迟从 500ms+ 降至 ~3ms；compile 后 daemon 自动重建连接零断连 |
| **0.8.0** | compile 后自动重连 automator；navigate 自动识别 TabBar 页面走 switchTab；screenshot 新增 full\_page/scroll\_top/page\_path 参数及视口截图模式；page\_data 新增 expected\_path 轮询防旧数据；长图拼接动态步长修复内容缺口；node\_bridge 统一连接断开重试 + 500ms 调用间隔；start 端口验证增至 20 次 |
| **0.7.0** | navigate 变量作用域修复（currentPageTimeout）；evaluate 支持声明语句（const/let/var fallback）；call_method 返回当前页面路径；automator start 端口轮询验证替代盲等；SKILL.md 新增效率原则、恢复分级、页面跳转方法、6 条故障条目 |
| **0.6.0** | navigate 支持 query 参数（reLaunch 超时 fallback）；CDP 启动噪音过滤（console.assert/\_\_route\_\_/ide:// 降噪 + WXML 错误保护）；compile 返回值三分类 + automator 失效提示；navigate currentPage 轮询重试；超时可配置 |
| **0.5.1** | `wechat_ide(action='open')` 新增 CDP 启动健康检查：自动采集 5 秒 CDP 日志检测启动阶段致命错误，有错误直接返回失败阻止后续操作 |
| **0.5.0** | Skill SOP 全面优化：新增 SOP I/J；增加 AppID 检查与 path 校验；CDP 噪音过滤；截图拼接模糊匹配修复 |
| **0.4.1** | 截图长页面拼接重写：固定区域检测、DPR 自适应、动态重叠计算 |
| **0.4.0** | CDP 日志增强、云函数部署自动验证、navigate 智能诊断、新增 SOP G/H |
| **0.3.0** | **重大重构**：44 个工具聚合为 8 个 API；CDP 日志 v2；新增 SKILL.md 知识库 |

<details>
<summary>更早版本</summary>

| 版本 | 说明 |
|------|------|
| 0.2.6 | README 新增 OpenAI Codex 配置说明 |
| 0.2.5 | 新增 Kiro 编辑器配置说明 |
| 0.2.4 | 截图滚动拼接修复：`sharp` → `jimp` |
| 0.2.3 | 发布包优化：排除 `scripts/` 源码，仅保留 `dist/` 构建产物 |
| 0.2.2 | Node.js 脚本改为 bundle-only 模式 |
| 0.2.1 | 版本更新与文档完善 |
| 0.2.0 | navigate 改用 CDP 高清日志采集 |
| 0.1.9 | 修复 UTF-8 编码乱码 |
| 0.1.8 | 修复 Windows 中文路径 UnicodeDecodeError |
| 0.1.7 | 新增 core/full 工具集预设；新增 MCP_DOC.md |
| 0.1.6 | `wechat_open(cdp_enabled=true)` 自动 kill 已有进程 |
| 0.1.5 | 修复 Windows stdio 阻塞问题 |
| 0.1.4 | 添加 CDP 日志、截图、自动化等功能 |
| 0.1.3 | 初始版本 |
</details>

---

## 参考文档

- [微信开发者工具 CLI 官方文档](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## 许可证

MIT
