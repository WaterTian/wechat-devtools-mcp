# 微信开发者工具 MCP Server (v0.1.6)

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 将微信开发者工具 CLI 封装为 [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) 服务，使编辑器中的 AI 能够直接调用微信 CLI 命令，实现小程序**开发、测试、调试、自动化**全流程闭环。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

🚀 **本 MCP Server 已正式提交至官方 [MCP Registry](https://modelcontextprotocol.io/)**，支持跨平台（Windows/macOS）一键安装。

当前版本：**v0.1.6**

---

## 🚀 安装与快速开始

> [!IMPORTANT]
> **在开始之前，请务必提前确认并准备好以下两个路径，您需要在编辑器配置中手动输入它们：**
>
> 1. **微信开发者工具 CLI 路径** (例如: `C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat`)
> 2. **您的小程序项目绝对路径** (例如: `D:\\MyProjects\\mini-app`)

### 1. 基础运行 (推荐)

如果你安装了 [uv](https://github.com/astral-sh/uv)，可以使用以下命令直接运行，或直接将其配置在编辑器中，而无需手动管理依赖：

```bash
uvx wechat-devtools-mcp
```

> [!TIP]
> 如果提示 `uvx` 命令找不到，请先执行 `pip install uv`。
> `uv tool list` 查看mcp版本
> `uv tool upgrade wechat-devtools-mcp` 升级全局工具wechat-devtools-mcp

### 2. 环境准备 (高级自动化功能必需)

部分高级功能（如 UI 点击、CDP 日志捕获等）依赖 Node.js 环境及自动化 SDK。由于 `uvx` 是在临时环境中运行，如果您需要使用这些自动化功能，必须先显式安装包并手动安装额外的 npm 依赖。

```bash
# 1. 显式全局安装包 (用于下载并定位脚本目录)
uv tool install wechat-devtools-mcp
# 或选用 pip install wechat-devtools-mcp

# 2. 查看包的实际安装路径
uv pip show wechat-devtools-mcp
# 或选用 pip show wechat-devtools-mcp

# 3. 在输出的结果中找到 "Location" 字段（例如 C:\Users\xxx\AppData\Local\Programs\Python\Python313\Lib\site-packages）
# 4. 进入相应的 scripts 目录并安装依赖：
cd "<Location路径>/wechat_devtools_mcp/scripts"
npm install
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

### Cursor / VS Code (MCP Plugin)

在 MCP 控制台中添加新 Server：

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: 同上添加 `WECHAT_DEVTOOLS_CLI` 和 `WECHAT_PROJECT_PATH`。

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
        "wechat_auto",
        "wechat_open",
        "wechat_is_login",
        "wechat_project_info",
        "wechat_list_pages",
        "wechat_read_page",
        "wechat_read_file",
        "wechat_compile_check",
        "wechat_get_cdp_logs",
        "wechat_get_console_logs",
        "wechat_get_exceptions",
        "wechat_capture_screenshot",
        "wechat_navigate_and_capture",
        "wechat_get_page_data",
        "wechat_get_page_stack",
        "wechat_tap_element",
        "wechat_input_element",
        "wechat_call_page_method",
        "wechat_evaluate_expression",
        "wechat_get_system_info",
        "wechat_get_status",
        "wechat_reset_fileutils",
        "wechat_cache_clean",
        "wechat_list_tools"
      ]
    }
  }
}
```

> `WECHAT_DEVTOOLS_CLI` 路径根据实际安装位置调整，注意反斜杠需要转义。

---

## 🛠️ 工具箱详解 (Toolbox Reference)

本项目提供 **44 个** MCP 工具，全方位覆盖小程序全生命周期：

### 1. 项目感知与上下文 (Context)

- `wechat_project_info`: 获取 `project.config.json` / `app.json` 配置及目录概览。
- `wechat_list_pages`: 列出所有注册页面及其文件存在状态。
- `wechat_read_page`: 一键读取指定页面的所有源码（WXML/JS/WXSS/JSON）。
- `wechat_read_file`: 读取项目中任意文件内容。

### 2. 构建、预览与编译 (Build)

- `wechat_compile_check`: **[最常用]** 触发编译并捕获所有 Error 和 Warning。
- `wechat_preview_page`: 快捷预览指定页面，支持携带 Query 参数并生成二维码。
- `wechat_build_npm`: 构建小程序 NPM 依赖。
- `wechat_upload`: 上传代码至微信后台，支持指定版本号和描述。
- `wechat_cache_clean`: 清除工具缓存（storage/compile/all 等）。
- `wechat_reset_fileutils`: 重建工具内部文件监听。

### 3. 自动化交互 (Automation v4.0)

需先调用 `wechat_auto` 开启 9420 自动化端口。

- `wechat_tap_element`: 通过 CSS 选择器模拟用户点击。
- `wechat_input_element`: 向 input/textarea 输入文本。
- `wechat_set_page_data`: **热更新**！直接修改渲染层 Data，免编译刷新预览。
- `wechat_call_page_method`: 调用页面中定义的各种 Logic 函数。
- `wechat_get_element_info`: 获取元素的 WXML、样式、坐标尺寸等详情。
- `wechat_mock_wx_method`: Mock 原生 API 返回值（如支付、位置等）。
- `wechat_call_wx_method`: 调用原生 `wx.xxx` 接口。
- `wechat_get_page_stack`: 获取当前活跃的页面导航栈。

### 4. 实时调试与日志 (Debug)

- `wechat_get_cdp_logs`: **[推荐]** 通过 CDP 协议（端口 9222）采集高清运行日志。能捕获 `wechat_get_console_logs` 无法获取的底层信息：WXML 语法警告、废弃 API 提示（如 `wx.getSystemInfoSync`、`wx.saveFile`）、渲染层网络报错等。**前提**：必须先以 `wechat_open(cdp_enabled=true)` 启动开发者工具。
- `wechat_get_console_logs`: 采集指定持续时间内的全量 console 输出。
- `wechat_get_exceptions`: 专门监听运行时的 JS Runtime 异常。
- `wechat_capture_screenshot`: 捕获当前小程序模拟器的全屏截图，自动滚动拼接长图并保存为 PNG。需指定 `output_path`（绝对路径）。**前提**：需先调用 `wechat_auto` 开启自动化端口。
- `wechat_navigate_and_capture`: 跳转指定页面并自动采集后续 N 秒的日志。
- `wechat_run_automation_script`: 执行自定义的 JS 自动化测试脚本。
- `wechat_get_system_info`: 获取小程序运行时的真实系统参数。
- `wechat_get_storage`: 读取小程序的本地持久化缓存。

### 5. 云开发管理 (Cloud)

- `wechat_cloud_env_list`: 查看当前 AppID 关联的所有云环境。
- `wechat_cloud_func_list` / `info`: 查阅线上云函数列表与配置。
- `wechat_cloud_func_deploy`: 部署、上传并自动安装云函数依赖。
- `wechat_cloud_func_download`: 下载线上云函数源码。

### 6. 系统诊断与管理

- `wechat_list_tools`: **[新]** 发现工具箱，分类展示所有可用能力。
- `wechat_get_status`: 检查 CLI 路径、项目路径及当前账号状态。
- `wechat_login` / `wechat_is_login`: 账号登录态管理。
- `wechat_close_project` / `wechat_quit_ide`: IDE 运行状态控制。

---

## 🎭 Mock 场景示例 (wechat_mock_wx_method)

`wechat_mock_wx_method` 工具可以覆盖 `wx` 对象上指定方法的返回值，让 AI 在无需真实设备权限或支付环境的情况下，模拟各类原生 API 的回调结果，用于自动化测试和功能验证。

> **注意：** Mock 仅在当前自动化会话中有效，重启开发者工具或重新调用 `wechat_auto` 后会自动失效，需重新设置。

### result_json 参数说明

`result_json` 是一个 **JSON 字符串**，其内容对应目标 wx API `success` 回调函数接收到的参数对象。例如 `wx.requestPayment` 成功时 `success` 回调不携带额外字段，因此传入 `{}` 即可；而 `wx.chooseLocation` 成功时会携带位置信息，需要在 `result_json` 中提供对应字段。

常见字段含义：

| 字段 | 所属 API | 说明 |
|------|----------|------|
| `errMsg` | 通用 | 错误信息，成功时格式为 `"apiName:ok"`，失败时包含原因 |
| `name` | `chooseLocation` | 位置名称 |
| `address` | `chooseLocation` | 详细地址 |
| `latitude` | `chooseLocation` | 纬度（浮点数） |
| `longitude` | `chooseLocation` | 经度（浮点数） |
| `tempFilePaths` | `chooseImage` | 选中图片的临时文件路径数组 |
| `tempFiles` | `chooseImage` | 选中图片的文件对象数组（含 `path` 和 `size`） |

### 场景一：支付成功

模拟 `wx.requestPayment` 调用成功，触发页面的支付成功逻辑分支：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "requestPayment",
    "result_json": "{\"errMsg\": \"requestPayment:ok\"}"
  }
}
```

### 场景二：支付失败（用户取消）

模拟用户主动取消支付，触发页面的取消/失败处理逻辑：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "requestPayment",
    "result_json": "{\"errMsg\": \"requestPayment:fail cancel\"}"
  }
}
```

> 提示：`fail cancel` 是微信支付用户取消时的标准 `errMsg` 格式，页面代码通常通过 `fail` 回调或 `errMsg.includes('cancel')` 来判断。

### 场景三：定位授权（chooseLocation）

模拟用户选择了一个位置，返回完整的位置信息：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "chooseLocation",
    "result_json": "{\"name\": \"腾讯北京总部\", \"address\": \"北京市海淀区科学院南路2号\", \"latitude\": 39.9842, \"longitude\": 116.3093, \"errMsg\": \"chooseLocation:ok\"}"
  }
}
```

### 场景四：相册选择（chooseImage）

模拟用户从相册选择了两张图片，返回临时文件路径：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "chooseImage",
    "result_json": "{\"tempFilePaths\": [\"wxfile://tmp_photo_001.jpg\", \"wxfile://tmp_photo_002.jpg\"], \"tempFiles\": [{\"path\": \"wxfile://tmp_photo_001.jpg\", \"size\": 102400}, {\"path\": \"wxfile://tmp_photo_002.jpg\", \"size\": 204800}], \"errMsg\": \"chooseImage:ok\"}"
  }
}
```

---

## 🤖 AI 协作 SOP (最佳实践)

为了达到最佳协作效果，建议按照以下工作流指挥 AI：

1. **环境检查与项目启动**:
    - 需先调用 `wechat_auto` 开启 9420 自动化端口。
    - 调用 `wechat_is_login` 确认登录状态。
    - 运行 `wechat_open(cdp_enabled=true)` 打开或刷新项目。**注意**：务必开启 `cdp_enabled: true` 以便后续能够采集到高清运行日志。此模式会自动关闭已有开发者工具实例再重新启动，确保 CDP 端口（9222）正确绑定。
    - 启动后建议**等待 3-5 秒**，确保小程序初始化加载完成。
2. **上下文理解**:
    - 调用 `wechat_project_info` 获取项目整体配置。
    - 调用 `wechat_read_page` 快速读取指定页面的所有相关代码（JS/WXML/WXSS/JSON）。
3. **循环开发迭代**:
    - **代码变更**：AI 根据需求修改代码。
    - **编译校验**：执行 `wechat_compile_check` 查看是否有编译错误。如有报错，AI 会根据报错信息自动进行修复。
    - **实时预览**：通过 `wechat_preview_page` 快速跳转到修改后的页面进行预览。
4. **深度调试与质量验收**:
    - **高清运行日志 (推荐)**：调用 `wechat_get_cdp_logs(duration=10)` 采集运行日志。它能捕获比 Console 更底层的信息，包括 WXML 警告、废弃 API 提示、渲染层报错等。建议在页面跳转后立即采集，以捕获 `onLoad` / `onShow` 阶段的完整输出。
    - **视觉截图验收**：调用 `wechat_capture_screenshot(output_path="<绝对路径>/screenshot.png")` 截取当前页面长图。截图会自动滚动拼接，适合全页面 UI 验收。需确保 `wechat_auto` 已开启。

---

## 💡 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | **[必须手动确认]** 微信开发者工具 CLI 路径 | 无 | **是** |
| `WECHAT_PROJECT_PATH` | **[必须手动确认]** 默认小程序项目绝对路径 | 无 | **是** |
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

### `wechat_get_cdp_logs` 报错 `Cannot find module './node_modules/ws'`

需要在 scripts 目录安装 Node.js 依赖：

```powershell
$scriptsDir = "C:\Users\$env:USERNAME\AppData\Roaming\uv\tools\wechat-devtools-mcp\Lib\site-packages\wechat_devtools_mcp\scripts"
Set-Location $scriptsDir
npm install
```

### 查看当前安装版本

```powershell
uv tool list
```

---

## 📋 版本历史

| 版本 | 说明 |
|------|------|
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
