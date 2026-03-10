# 微信开发者工具 MCP Server

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 将微信开发者工具 CLI 封装为 [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) 服务，使编辑器中的 AI 能够直接调用微信 CLI 命令，实现小程序**开发、测试、调试、自动化**全流程闭环。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

🚀 **本 MCP Server 已正式提交至官方 [MCP Registry](https://modelcontextprotocol.io/)**，支持跨平台（Windows/macOS）一键安装。

---

## 🛠️ 工具箱详解 (Toolbox Reference)

本项目提供超过 30 个 MCP 工具，按开发阶段分为以下六大核心模块：

### 1. 项目感知与上下文 (Context)

在修改代码前，调用这些工具让 AI 了解你的小程序。

- `wechat_project_info`: 获取 `project.config.json` / `app.json` 配置及目录概览。
- `wechat_list_pages`: 列出所有注册页面及其 `.wxml/.js/.wxss/.json` 文件状态。
- `wechat_read_page`: 一键读取指定页面的所有源码（含逻辑、结构与样式）。
- `wechat_read_file`: 读取项目中任意文件内容。

### 2. 基础操作与生命周期

- `wechat_open`: 打开 IDE 或指定项目。建议开启 `cdp_enabled: true`。
- `wechat_login`: 生成控制台/文件二维码进行扫码登录。
- `wechat_is_login`: 快速检查当前登录状态。
- `wechat_close_project` / `wechat_quit_ide`: 管理窗口状态。

### 3. 构建、预览与编译 (Build)

- `wechat_compile_check`: **[最常用]** 触发编译并捕获所有 Error 和 Warning，AI 调试的核心。
- `wechat_preview_page`: 快捷预览指定页面，支持携带 Query 参数。
- `wechat_build_npm`: 触发项目 NPM 构建。
- `wechat_upload`: 一键上传代码至微信后台。

### 4. 自动化交互 (Automation v4.0)

通过代码控制小程序 UI，需先调用 `wechat_auto` 开启 9420 端口。

- `wechat_tap_element`: 通过 CSS 选择器（如 `.btn`）模拟用户点击。
- `wechat_input_element`: 模拟输入框/文本域内容输入。
- `wechat_set_page_data`: **热更新**！直接修改页面 `Data` 状态，免编译查看 UI。
- `wechat_call_wx_method`: 直接调用原生 `wx.xxx` 接口。
- `wechat_page_stack`: 获取当前活跃的页面栈。

### 5. 深度垂直调试 (Debug)

- `wechat_get_cdp_logs`: **[推荐]** 捕获 WXML 警告、底层网络报错。
- `wechat_get_console_logs`: 采集指定时间段内的页面 `console` 输出。
- `wechat_capture_screenshot`: 捕获当前小程序画面的全屏截图（用于 UI 验收）。

### 6. 云开发管理 (Cloud)

- `wechat_cloud_func_list` / `info`: 查阅线上云函数状态。
- `wechat_cloud_func_deploy`: 部署/更新指定云函数。
- `wechat_cloud_func_download`: 下载线上云函数源码。

---

## 🤖 AI 协作 SOP (最佳实践)

为了达到最佳协作效果，建议按照以下工作流指挥 AI：

1. **环境检查**: `wechat_is_login` -> `wechat_open(cdp_enabled=true)`
2. **上下文理解**: `wechat_project_info` -> `wechat_read_page(page_path='pages/index/index')`
3. **循环开发迭代**:
    - (你或 AI 修改代码)
    - 调用 `wechat_compile_check`。如有报错，将报错贴给 AI 修复。
    - 调用 `wechat_preview_page` 查看真机/模拟器效果。
4. **UI/逻辑验收**:
    - 调用 `wechat_auto` 开启引擎。
    - 执行 `wechat_tap_element` 触发逻辑，配合 `wechat_capture_screenshot` 截图确认。

---

## 💡 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | 微信开发者工具 CLI 路径 | 无 | **是** |
| `WECHAT_PROJECT_PATH` | 默认小程序项目绝对路径 | 无 | **是** |
| `WECHAT_CLI_TIMEOUT` | CLI 命令超时时间（秒） | `60` | 否 |
| `NODE_PATH` | Node.js 执行文件路径 | `node` | 否 |

---

## 参考文档

- [微信开发者工具 CLI 官方文档](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## 许可证

MIT
