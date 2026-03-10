# 微信开发者工具 MCP Server

[![PyPI version](https://img.shields.io/pypi/v/wechat-devtools-mcp.svg)](https://pypi.org/project/wechat-devtools-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue.svg)](https://modelcontextprotocol.io/docs/concepts/mcp-registry)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 将微信开发者工具 CLI 封装为 [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) 服务，使编辑器中的 AI 能够直接调用微信 CLI 命令，实现小程序**开发、测试、调试、自动化**全流程闭环。

<!-- mcp-name: io.github.WaterTian/wechat-devtools-mcp -->

🚀 **本 MCP Server 已正式提交至官方 [MCP Registry](https://modelcontextprotocol.io/)**，支持跨平台（Windows/macOS）一键安装。

---

## 安装与快速开始

### 1. 一键运行 (推荐)

如果你安装了 [uv](https://github.com/astral-sh/uv)，可以使用以下命令直接在 Claude Desktop 或 Cursor 中调用，无需手动安装：

```bash
uvx wechat-devtools-mcp
```

### 2. 通过 pip 安装

```bash
pip install wechat-devtools-mcp
```

### 3. 环境准备 (自动化功能必需)

部分高级功能（如 UI 点击、CDP 日志捕获等）依赖 `miniprogram-automator`。安装 Python 包后，需确保您的 Node.js 环境已就绪：

```bash
# 进入包安装目录执行（通常在 site-packages/wechat_devtools_mcp/scripts）
npm install
```

---

## 编辑器配置

### Claude Desktop

修改 `claude_desktop_config.json`：

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

### Cursor / VS Code (MCP Plugin)

在 MCP 控制台中添加新 Server：

- **Name**: `wechat-devtools`
- **Type**: `command`
- **Command**: `uvx wechat-devtools-mcp`
- **Environment Variables**: 同上添加 `WECHAT_DEVTOOLS_CLI` 和 `WECHAT_PROJECT_PATH`。

---

## 能力概览

### v4.0 — 自动化交互

| 能力 | 说明 |
|------|------|
| **点击 UI 元素** | 通过 CSS 选择器模拟 `tap` 点击任意元素 |
| **表单输入** | 向 `input` / `textarea` 输入文本内容 |
| **修改页面 Data** | 动态 `setData` 热更新 UI，免编译 |
| **调用页面方法** | 远程触发 `onPullDownRefresh` 等页面方法 |
| **获取元素详情** | 读取元素 text / wxml / style / size / offset |
| **Mock wx API** | 覆盖 `showModal`、`chooseLocation` 等系统调用返回值 |
| **调用 wx API** | 直接执行 `wx.setNavigationBarTitle` 等接口 |
| **页面导航栈** | 查看完整的页面栈信息 |

### v3.x — 实时调试
>
> 💡 **核心建议**：在排查问题和采集日志时，**强烈建议直接使用 `wechat_get_cdp_logs`获取 CDP 高清日志**。

| 能力 | 说明 |
|------|------|
| **CDP 高清日志** | 🆕 **[推荐]** 捕获底层 WXML 警告、网络报错、系统事件和完整堆栈 |
| **Console 日志** | 实时捕获页面层级 `console.log/warn/error` 输出 |
| **异常监控** | 监听 JS 异常（含完整调用栈） |
| **持久连接** | 自动化端口一次开启常驻，多工具顺序调用无需重连 |

---

---

## 参考文档

- [微信开发者工具 CLI](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
- [小程序自动化 SDK](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/quick-start.html)

---

## 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `WECHAT_DEVTOOLS_CLI` | 微信开发者工具 CLI 路径 | 无 | **是** |
| `WECHAT_PROJECT_PATH` | 默认小程序项目绝对路径 | 无 | **是** |
| `WECHAT_CLI_TIMEOUT` | CLI 命令超时时间（秒） | `60` | 否 |
| `NODE_PATH` | Node.js 可执行文件路径 | `node` | 否 |

---

## AI 开发工作流指南

1. **理解上下文**: `wechat_project_info` + `wechat_read_page`
2. **执行修改**: (编写代码) -> `wechat_compile_check` (检查编译)
3. **效果预览**: `wechat_preview_page`
4. **自动化巡检**: `wechat_auto` -> `wechat_capture_screenshot` -> `wechat_get_cdp_logs`

---

## 目录结构 (源码)

```
wechat-devtools-mcp/
├── pyproject.toml             # Python 项目定义
├── server.json                # MCP Registry 元数据
├── LICENSE                    # MIT 许可证
├── src/
│   └── wechat_devtools_mcp/
│       ├── server.py          # MCP Server 主入口
│       └── scripts/           # Node.js 辅助脚本
```

## 许可证

MIT
