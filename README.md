# 微信开发者工具 MCP Server (v0.3.0)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 将微信开发者工具 CLI 封装为 [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) 服务，使编辑器中的 AI 能够直接调用微信 CLI 命令，实现小程序**开发、测试、调试、自动化**全流程闭环。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

🚀 **本 MCP Server 已正式提交至官方 [MCP Registry](https://modelcontextprotocol.io/)**，支持跨平台（Windows/macOS）一键安装。


---

## 🚀 安装与快速开始

> [!IMPORTANT]
> **在开始之前，请务必提前确认并准备好以下两个路径，您需要在编辑器配置中手动输入它们：**
>
> 1. **微信开发者工具 CLI 路径** (例如: `C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat`)
> 2. **您的小程序项目绝对路径** (例如: `D:\\MyProjects\\mini-app`)

### 1. 基础环境准备

如果你安装了 [uv](https://github.com/astral-sh/uv)，可以使用以下命令直接运行，或直接将其配置在编辑器中，而无需手动管理依赖：

```bash
uvx wechat-devtools-mcp
```


> [!TIP]
> 如果提示 `uvx` 命令找不到，请先执行 `pip install uv`。
> `uv tool list` 查看mcp版本
> `uv tool upgrade wechat-devtools-mcp` 升级全局工具wechat-devtools-mcp


```bash
# 1. 隔离环境安装包 (独立工具) 
uv tool install wechat-devtools-mcp --force

# 2. 查看独立工具包的环境安装目录
uv tool dir


```

## ⚙️ 编辑器配置

### Claude Desktop / Antigravity

修改 `claude_desktop_config.json` 或 `mcp_config.json` (Antigravity)：

```json
{
  "mcpServers": {
    "wechat-devtools": {
      "command": "uvx",
      "args": ["wechat-devtools-mcp@latest"],
      "env": {
        "WECHAT_DEVTOOLS_CLI": "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat",
        "WECHAT_PROJECT_PATH": "D:\\Your\\Project\\Path"
      }
    }
  }
}
```


### Kiro

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
        "wechat_ide",
        "wechat_build",
        "wechat_automator",
        "wechat_inspector",
        "wechat_screenshot",
        "wechat_navigate",
        "wechat_file",
        "wechat_cloud"
      ]
    }
  }
}
```

### OpenAI Codex

编辑 `~/.codex/config.toml`（全局）或项目根目录下的 `.codex/config.toml`（项目级）：

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

> 配置完成后，在 Codex TUI 中输入 `/mcp` 可查看已激活的 MCP 服务。

---

### Cursor / VS Code (MCP Plugin)

在 MCP 控制台中添加新 Server：

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: 同上添加 `WECHAT_DEVTOOLS_CLI` 和 `WECHAT_PROJECT_PATH`。

> `WECHAT_DEVTOOLS_CLI` 路径根据实际安装位置调整，注意反斜杠需要转义。

---

## 🛠️ 工具箱概要 (Toolbox Reference)

v0.3.0 采用「**瘦 MCP + 胖 Skill**」架构，提供 **8 个聚合工具**，覆盖小程序全生命周期。

| 工具 | 功能 | 支持的 action |
|------|------|--------------|
| `wechat_ide` | IDE 生命周期管理 | open, login, is_login, close, quit, status |
| `wechat_build` | 构建与发布 | compile, preview, upload, build_npm, cache_clean |
| `wechat_automator` | 自动化交互 | start, tap, input, element_info, set_data, call_method, call_wx, mock_wx, evaluate, page_stack, page_data, system_info, storage |
| `wechat_inspector` | 运行时日志采集 | console, cdp |
| `wechat_screenshot` | 界面截图（长图拼接） | — |
| `wechat_navigate` | 跳转页面并采集 CDP 日志 | — |
| `wechat_file` | 项目文件读取 | project_info, list_pages, read_page, read_file |
| `wechat_cloud` | 云函数管理 | env_list, func_list, func_info, func_deploy, func_download |

完整工具参数说明请参阅 **[MCP_DOC.md](./MCP_DOC.md)**。

---

## 🤖 AI 协作 SOP (最佳实践)

### SOP 一：日常开发迭代

适用于日常功能开发、Bug 修复场景。

**Step 1 — 初始化环境**

```
wechat_ide(action='status')           # 诊断环境配置
wechat_ide(action='is_login')         # 检查登录状态
wechat_ide(action='open', cdp_enabled=True)   # 开启 IDE + CDP 端口
wechat_automator(action='start')      # 开启自动化端口 9420
```

**Step 2 — 读取上下文**

```
wechat_file(action='project_info')    # 获取项目完整信息
wechat_file(action='list_pages')      # 获取页面列表
```

直接在编辑器中打开目标页面的源码文件（JS/WXML/WXSS/JSON），按需修改代码。

**Step 3 — 编译验证（循环）**

```
修改代码 → wechat_build(action='compile') → 有报错则修复 → 再次 compile
```

**Step 4 — 调试验收**

```
wechat_navigate(page_path="pages/xxx/xxx", wait_ms=3000)
  ↓ 跳转页面，CDP 采集高清日志（WXML 警告、废弃 API、渲染层报错等）

wechat_screenshot(output_path="D:/screenshots/xxx.png")
  ↓ 全页面长图截图验收
```

---

### SOP 二：全页面巡检（截图 + 高清日志）

适用于回归测试、UI 验收、发布前全量检查。

> **前提**：已完成 SOP 一的 Step 1 初始化，且 `cdp_enabled=True`。

**Step 1 — 获取页面列表**

```
wechat_file(action='list_pages')
```

**Step 2 — 对每个页面依次执行（循环）**

> ⚠️ **重要**：必须按顺序逐个页面执行，不可并行。

```
① wechat_navigate(page_path="<页面路径>", wait_ms=3000)
     ↓ 跳转到目标页面，采集 CDP 高清日志

② wechat_screenshot(output_path="<输出目录>/<页面名>.png")
     ↓ 截取当前页面长图并保存

③ 重复步骤 ① 和 ②，直到所有页面巡检完成
```

**Step 3 — 汇总分析**

AI 对所有页面的日志和截图进行汇总，输出：
- 各页面是否存在 JS 异常 / WXML 警告 / 废弃 API
- 截图路径列表，供人工 UI 核查

**完整指令示例（直接发给 AI）：**

```
请对项目所有页面进行全量巡检：
1. 调用 wechat_file(action='list_pages') 获取页面列表
2. 对每个页面依次执行：
   - wechat_navigate 跳转并采集 CDP 高清日志（wait_ms=3000）
   - wechat_screenshot 截图保存到 D:/screenshots/<页面名>.png
3. 最后汇总所有页面的异常和警告（cdp_logs.summary）
```

---

## 💡 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | **[必须手动确认]** 微信开发者工具 CLI 路径 | 无 | **是** |
| `WECHAT_PROJECT_PATH` | **[必须手动确认]** 默认小程序项目绝对路径 | 无 | **是** |
| `WECHAT_CLI_TIMEOUT` | CLI 命令超时时间（秒） | `30` | 否 |
| `NODE_PATH` | Node.js 执行文件路径 | `node` | 否 |

---

## 🔄 升级

```powershell
# 先终止占用进程
Get-Process | Where-Object { $_.ProcessName -like "*wechat-devtools*" } | Stop-Process -Force
# 重新安装最新版
uv tool install wechat-devtools-mcp --reinstall
```

---

## ❓ 常见问题

### `uv tool upgrade` 报错"另一个程序正在使用此文件"

MCP 服务进程仍在运行，需先终止：

```powershell
Get-Process | Where-Object { $_.ProcessName -like "*wechat-devtools*" } | Stop-Process -Force
Start-Sleep -Seconds 2
uv tool install wechat-devtools-mcp --reinstall
```

### `wechat_inspector(action='cdp')` 返回"CDP 采集失败"

开发者工具已有实例运行时，`--remote-debugging-port` 参数会被忽略，导致 9222 端口未绑定。解决方法：**不要手动启动开发者工具**，直接调用 `wechat_ide(action='open', cdp_enabled=True)`，它会自动 kill 已有进程并以 CDP 模式重新启动。

### 查看当前安装版本

```powershell
uv tool list
```

---

## 📋 版本历史

| 版本 | 说明 |
|------|------|
| 0.3.0 | **重大重构**：44 个工具聚合为 8 个 API（`wechat_ide/build/automator/inspector/screenshot/navigate/file/cloud`）；server.py 从 3175 行压缩为 60 行；CDP 日志 v2（结构化 JSON + detail_level + max_logs）；新增 `cdp_core.js` 共享模块；新增 SKILL.md 知识库 |
| 0.2.6 | 文档更新：README 编辑器配置章节新增 OpenAI Codex 配置说明 |
| 0.2.5 | 新增 Kiro 编辑器配置说明 |
| 0.2.4 | 截图滚动拼接修复：将 `sharp` 替换为纯 JS 的 `jimp` |
| 0.2.3 | 发布包优化：排除 `scripts/` 源码文件，仅保留 `scripts/dist/` 构建产物 |
| 0.2.2 | `wechat_get_cdp_logs` 移入 core 预设；Node.js 脚本改为 bundle-only 模式 |
| 0.2.1 | 版本更新与文档完善 |
| 0.2.0 | `wechat_navigate_and_capture` 改用 CDP 高清日志采集；core 预设精简为 13 个核心工具 |
| 0.1.9 | fix: 修复源码文件 UTF-8 编码乱码问题 |
| 0.1.8 | fix: Windows 下 uvx 启动时中文路径导致 UnicodeDecodeError |
| 0.1.7 | 新增 `WECHAT_TOOLS_PRESET` core/full 工具集预设；新增 MCP_DOC.md |
| 0.1.6 | `wechat_open(cdp_enabled=true)` 自动 kill 已有进程 |
| 0.1.5 | 修复 Windows 平台 stdio 阻塞问题 |
| 0.1.4 | 添加 CDP 日志、截图、自动化等功能 |
| 0.1.3 | 初始版本 |

---

## 🧠 AI Skill（智能协作知识库）

本项目提供配套的 **wechat-devtools Skill**，可让支持 [Agent Skills](https://skills.sh/) 协议的 AI 编辑器（如 Kiro、Antigravity 等）自动加载 SOP 流程、参数速查和最佳实践，无需每次手动提示。

### 安装 Skill

**方式一：通过 GitHub 仓库引用（推荐）**

```bash
npx skills add WaterTian/wechat-devtools-mcp/.agents/skills/wechat-devtools
```

**方式二：手动复制**

将 `.agents/skills/wechat-devtools/` 目录复制到你的项目或全局 skills 目录：

```
.agents/skills/
└── wechat-devtools/
    ├── SKILL.md                    # 主指令文件（SOP + 能力映射 + 红线规则）
    └── references/
        └── tool_reference.md       # 8 个聚合 API 完整参数参考
```

### Skill 包含内容

- **5 个 SOP 流程**：初始化、UI 调试、异常排查、全页面巡检、Mock 集成测试
- **能力映射字典**：8 个聚合工具 × 全部 action 的快速索引
- **CDP 渐进排查策略**：concise → full 两阶段，控制 Token 消耗
- **完整参数参考**：每个 action 的必填/可选参数、返回示例、常用模板
- **故障排查手册**：常见错误码与修复方式

### 使用方式

安装 Skill 后，在 AI 编辑器中直接描述意图即可，AI 会自动匹配对应 SOP：

```
"帮我检查所有页面有没有报错"     → 自动执行 SOP D（全页面巡检）
"点击登录按钮，截图看看效果"     → 自动执行 SOP B（UI 调试流）
"页面白屏了，帮我排查"           → 自动执行 SOP C（异常排查流）
"Mock 支付接口，测试支付流程"    → 自动执行 SOP E（Mock 集成测试）
```

---

## 参考文档

- [微信开发者工具 CLI 官方文档](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## 许可证

MIT
