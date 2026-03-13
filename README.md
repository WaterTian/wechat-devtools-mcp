# 微信开发者工具 MCP Server (v0.2.4)

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
        "WECHAT_PROJECT_PATH": "D:\\Your\\Project\\Path",
        "WECHAT_TOOLS_PRESET": "core"
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
        "PYTHONIOENCODING": "utf-8",
        "WECHAT_TOOLS_PRESET": "core"
      },
      "autoApprove": [
        "wechat_setup_sop",
        "wechat_open",
        "wechat_is_login",
        "wechat_auto",
        "wechat_compile_check",
        "wechat_cache_clean",
        "wechat_tap_element",
        "wechat_input_element",
        "wechat_navigate_and_capture",
        "wechat_capture_screenshot",
        "wechat_get_cdp_logs",
        "wechat_list_pages",
        "wechat_get_status",
        "wechat_list_tools"
      ]
    }
  }
}
```

### Cursor / VS Code (MCP Plugin)

在 MCP 控制台中添加新 Server：

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: 同上添加 `WECHAT_DEVTOOLS_CLI` 和 `WECHAT_PROJECT_PATH`。

> `WECHAT_DEVTOOLS_CLI` 路径根据实际安装位置调整，注意反斜杠需要转义。

---

## 🛠️ 工具箱概要 (Toolbox Reference)

本项目提供 **44 个** MCP 工具，覆盖小程序全生命周期，分为六大类。

默认 `core` 预设开放 **14 个**核心工具（覆盖两个 SOP 流程），设置 `WECHAT_TOOLS_PRESET=full` 可开放全部工具。

| 分类 | core 预设 | full 预设额外增加 |
|------|-----------|-----------------|
| 项目感知与上下文 | `wechat_list_pages` | `wechat_project_info`, `wechat_read_page`, `wechat_read_file` |
| 构建、预览与编译 | `wechat_compile_check`, `wechat_cache_clean` | `wechat_preview`, `wechat_preview_page`, `wechat_build_npm`, `wechat_upload`, `wechat_reset_fileutils` |
| 自动化交互 | `wechat_auto`, `wechat_tap_element`, `wechat_input_element` | `wechat_set_page_data`, `wechat_get_page_data`, `wechat_call_page_method`, `wechat_get_element_info`, `wechat_mock_wx_method`, `wechat_call_wx_method`, `wechat_get_page_stack`, `wechat_evaluate_expression`, `wechat_auto_replay` |
| 实时调试与日志 | `wechat_navigate_and_capture`, `wechat_capture_screenshot`, `wechat_get_cdp_logs` | `wechat_get_console_logs`, `wechat_get_exceptions`, `wechat_get_system_info`, `wechat_get_storage` |
| 云开发管理 | — | `wechat_cloud_env_list`, `wechat_cloud_func_list`, `wechat_cloud_func_info`, `wechat_cloud_func_deploy`, `wechat_cloud_func_download` |
| 系统诊断与管理 | `wechat_setup_sop`, `wechat_open`, `wechat_is_login`, `wechat_get_status`, `wechat_list_tools` | `wechat_login`, `wechat_close_project`, `wechat_quit_ide` |

完整工具参数说明请参阅 **[MCP_DOC.md](./MCP_DOC.md)**。

---

## 🤖 AI 协作 SOP (最佳实践)

### SOP 一：日常开发迭代

适用于日常功能开发、Bug 修复场景。

**Step 1 — 一键初始化**

```
调用 wechat_setup_sop(cdp_enabled=true)
```

一次调用完成：登录检查 → 自动化端口开启 → 项目打开（含 CDP）→ 项目信息获取。

**Step 2 — 读取上下文**

```
直接在编辑器中打开目标页面的源码文件（JS/WXML/WXSS/JSON），按需修改代码。

```

**Step 3 — 编译验证（循环）**

```
修改代码 → wechat_compile_check() → 有报错则修复 → 再次 compile_check
```

**Step 4 — 调试验收**

```
wechat_navigate_and_capture(page_path="pages/xxx/xxx", wait_ms=3000)
  ↓ 跳转页面，通过 CDP 采集高清日志（WXML 警告、废弃 API、渲染层报错、JS 异常等）

wechat_capture_screenshot(output_path="D:/screenshots/xxx.png")
  ↓ 全页面长图截图验收
```

---

### SOP 二：全页面巡检（截图 + 高清日志）

适用于回归测试、UI 验收、发布前全量检查。逐一遍历所有页面，截图并采集高清日志。

> **前提**：`wechat_setup_sop` 已完成初始化，且 `cdp_enabled=true`。

**Step 1 — 获取页面列表**

```
调用 wechat_list_pages()
```

获取 `app.json` 中所有注册页面的路径列表。

**Step 2 — 对每个页面依次执行以下操作（循环）**

> ⚠️ **重要**：必须按顺序逐个页面执行，不可并行。每个页面完成截图后再跳转下一个。

```
① wechat_navigate_and_capture(page_path="<页面路径>", wait_ms=3000)
     ↓ 跳转到目标页面，等待 3 秒加载完成，通过 CDP 采集高清日志（WXML 警告、废弃 API、渲染层报错、JS 异常等）

② wechat_capture_screenshot(output_path="<输出目录>/<页面名>.png")
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
1. 调用 wechat_list_pages 获取页面列表
2. 对每个页面依次执行：
   - wechat_navigate_and_capture 跳转并采集 CDP 高清日志（wait_ms=3000）
   - wechat_capture_screenshot 截图保存到 D:/screenshots/<页面名>.png
3. 最后汇总所有页面的异常和警告
```

---

## 💡 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | **[必须手动确认]** 微信开发者工具 CLI 路径 | 无 | **是** |
| `WECHAT_PROJECT_PATH` | **[必须手动确认]** 默认小程序项目绝对路径 | 无 | **是** |
| `WECHAT_TOOLS_PRESET` | 工具集预设：`core`（SOP + 调试核心，约 13 个）或 `full`（全部 44 个） | `core` | 否 |
| `WECHAT_CLI_TIMEOUT` | CLI 命令超时时间（秒） | `60` | 否 |
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

### `wechat_get_cdp_logs` 返回"未发现新日志"

开发者工具已有实例运行时，`--remote-debugging-port` 参数会被忽略，导致 9222 端口未绑定。解决方法：**不要手动启动开发者工具**，直接调用 `wechat_open(cdp_enabled=true)`，它会自动 kill 已有进程并以 CDP 模式重新启动。



### 查看当前安装版本

```powershell
uv tool list
```

---

## 📋 版本历史

| 版本 | 说明 |
|------|------|
| 0.2.4 | 截图滚动拼接修复：将 `sharp`（原生 addon，ncc 无法打包）替换为纯 JS 的 `jimp`，bundle 现可完整包含图片拼接逻辑，无需外部依赖 |
| 0.2.3 | 发布包优化：排除 `scripts/` 文件（`.js`、`.json`、`.sh`、`.bat`、`node_modules`），仅保留 `scripts/dist/` 构建产物 |
| 0.2.2 | `wechat_get_cdp_logs` 移入 core 预设（core 工具数升至 14 个）；Node.js 脚本改为 bundle-only 模式，移除 npm install fallback，用户无需手动安装依赖 |
| 0.2.1 | 版本更新与文档完善 |
| 0.2.0 | `wechat_navigate_and_capture` 改用 CDP 高清日志采集；core 预设精简为 13 个核心工具（新增 `wechat_tap_element`、`wechat_input_element`、`wechat_cache_clean`）；删除 `wechat_run_automation_script`；更新 SOP 文档 |
| 0.1.9 | fix: 修复源码文件 UTF-8 编码乱码问题 |
| 0.1.8 | fix: Windows 下 uvx 启动时中文路径导致 UnicodeDecodeError，强制 stdio UTF-8 编码 |
| 0.1.7 | 新增 `WECHAT_TOOLS_PRESET` core/full 工具集预设（core 默认开放 18 个核心工具）；新增完整工具参考文档 MCP_DOC.md；重构 SOP 文档，新增全页面巡检 SOP |
| 0.1.6 | `wechat_open(cdp_enabled=true)` 自动 kill 已有进程，确保 CDP 端口（9222）正确绑定 |
| 0.1.5 | 修复 Windows 平台 stdio 阻塞问题（临时文件方案） |
| 0.1.4 | 添加 CDP 日志、截图、自动化等功能 |
| 0.1.3 | 初始版本 |

---

## 参考文档

- [微信开发者工具 CLI 官方文档](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## 许可证

MIT
