---
name: wechat-devtools
description: |
  微信小程序开发调试知识库。提供 8 个聚合 API 的 SOP 流程、参数速查和最佳实践。
  当需要使用微信开发者工具 MCP（wechat_ide / wechat_build / wechat_automator 等）时使用本 Skill。
---

# Wechat DevTools MCP Skill

## 前置条件

### Step 0：安装与配置

```bash
pip install uv   # 如未安装 uv
uv tool install wechat-devtools-mcp --force  # 通过uv安装wechat-devtools-mcp
```

编辑器配置：

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

> 主流编辑器配置见 [README.md](https://github.com/WaterTian/wechat-devtools-mcp#%EF%B8%8F-%E7%BC%96%E8%BE%91%E5%99%A8%E9%85%8D%E7%BD%AE)

> [!IMPORTANT]
> **必须手动开启开发者工具的服务端口**：`设置` → `安全设置` → `服务端口` → `开启`。未开启将导致所有 CLI 操作报 `CLI_TIMEOUT`。

### Step 1：运行时环境检查

> 首先调用 `wechat_ide(action='status')` 一次性确认所有前置条件。

| 检查项 | 偏好命令 | 失败时操作 |
|--------|---------|----------|
| CLI 已安装 | `status` → `cli_exists: true` | 安装工具并配置 `WECHAT_DEVTOOLS_CLI` |
| 项目路径已配置 | `status` → `project_exists: true` | 配置 `WECHAT_PROJECT_PATH` |
| 已登录 | `is_login` → `logged_in: true` | `login(qr_format='terminal')` 扫码 |
| Node.js 可用 | `status` → `node_available: true` | 安装 Node.js ≥ 8.0 |

---

## API 速查表

### `wechat_ide` — IDE 生命周期

| action | 功能 | 关键参数 |
|--------|------|---------|
| `open` | 打开 IDE/项目 | `cdp_enabled=true`（开启 CDP 9222 端口） |
| `login` | 扫码登录 | `qr_format="terminal"` |
| `is_login` | 检查登录状态 | — |
| `close` / `quit` | 关闭项目 / 退出 IDE | — |
| `status` | 环境诊断 | — |

### `wechat_build` — 构建与发布

| action | 功能 | 关键参数 |
|--------|------|---------|
| `compile` | 编译检查（捕获错误/警告） | — |
| `preview` | 生成预览二维码 | `qr_format="terminal"` |
| `upload` | 上传到微信后台 | **`version`（必填）**, `desc?` |
| `build_npm` | 构建 NPM 依赖（upload 前必做） | — |
| `cache_clean` | 清除缓存 | `clean_type="compile"` |

### `wechat_automator` — 自动化交互

> **前提**：先调用 `start` 开启自动化端口（整个会话仅需一次）。

| action | 功能 | 必填参数 |
|--------|------|---------|
| `start` | 开启自动化端口 | — |
| `tap` | 点击元素 | `selector` |
| `input` | 输入文本 | `selector`, `value` |
| `element_info` | 获取元素详情（文本/尺寸/WXML） | `selector` |
| `set_data` | 热更新页面 data（无需重编译） | `data_json` |
| `call_method` | 调用页面方法 | `method`, `args_json?` |
| `call_wx` | 调用 wx API | `method` |
| `mock_wx` | Mock wx API 返回值 | `method`, `result_json` |
| `evaluate` | 执行 JS 表达式（逻辑层万能钥匙） | `expression` |
| `page_stack` | 获取页面栈 | — |
| `page_data` | 获取当前页面 data | — |
| `system_info` | 获取运行时系统信息 | — |
| `storage` | 读取本地缓存 | `key?`（空=列出全部） |

### `wechat_inspector` — 日志采集

| action | 功能 | 关键参数 |
|--------|------|---------|
| `console` | 采集 console 日志和 JS 异常 | `duration=10`, `log_type="all"` |
| `cdp` | CDP 协议采集底层日志（WXML/渲染层） | `duration=10`, `detail_level="concise"`, `max_logs=50` |

> **cdp 前提**：以 `cdp_enabled=true` 打开项目，确保端口 9222 可用。

### `wechat_screenshot` — 截图

- `output_path`（**必填**）：绝对路径，例如 `C:\tmp\shot.png`
- **前提**：先调用 `wechat_automator(action='start')`

### `wechat_navigate` — 跳转并采集日志

- `page_path`（**必填**）：如 `pages/index/index`
- `wait_ms`：等待毫秒，建议 3000
- `detail_level`：`concise`（仅 errors+warnings）或 `full`
- **前提**：需 `automator start` + `cdp_enabled=true`

### `wechat_file` — 文件读取

| action | 功能 | 必填参数 |
|--------|------|---------|
| `project_info` | 项目完整信息（app.json + 目录结构） | — |
| `list_pages` | 所有页面列表（含文件完整性检查） | — |
| `read_page` | 读取页面源码（wxml/wxss/js/json） | `page_path` |
| `read_file` | 读取任意单文件（最多 800 行） | `file_path` |

### `wechat_cloud` — 云函数管理

| action | 功能 | 必填参数 |
|--------|------|---------|
| `env_list` | 列出云环境 | — |
| `func_list` | 列出云函数 | `env` |
| `func_info` | 获取云函数详情 | `env`, `names` |
| `func_deploy` | 上传云函数 | `env` |
| `func_download` | 下载云函数 | `env`, `name`, `download_path` |

---

## SOP 标准操作流程

### SOP A：初始化（新环境必做）

```
wechat_ide(action='status')                         # 诊断环境
wechat_ide(action='is_login')                       # 检查登录
  ↳ 未登录: wechat_ide(action='login', qr_format='terminal')
wechat_ide(action='open', cdp_enabled=True)         # 开启 IDE + CDP 9222
wechat_automator(action='start')                    # 开启自动化 9420，等待 3s
wechat_file(action='project_info')                  # [可选] 确认项目结构
```

### SOP B：UI 调试（数据/布局问题）

```
wechat_navigate(page_path='pages/xxx/xxx', wait_ms=3000)   # 跳转 + CDP 日志
wechat_screenshot(output_path='C:\tmp\debug.png')          # 截图查看布局
wechat_automator(action='page_data')                       # 查看 data 状态
  ↳ 数据异常: set_data(data_json='{"key":"val"}')  热更新验证
  ↳ 确认元素: element_info(selector='.target')
```

### SOP C：异常排查（报错/白屏/JS 异常）

```
wechat_inspector(action='cdp', duration=5, detail_level='concise')
  ↳ summary.errors > 0 → 改用 detail_level='full' 查完整上下文
wechat_inspector(action='console', duration=5, log_type='exception')   # JS 异常堆栈
wechat_file(action='read_page', page_path='pages/xxx/xxx')             # 读源码定位
wechat_build(action='compile')                                          # 捕获静态错误
```

### SOP D：全页面巡检（回归/发布前验收）

```
wechat_file(action='list_pages')                    # 获取页面列表
# 对每个 page 顺序执行（禁止并行）：
wechat_navigate(page_path=page, wait_ms=3000)       # 跳转 + 采集 CDP summary
wechat_screenshot(output_path=f'C:\tmp\{page}.png') # 截图保存
# 汇总 summary.errors / warnings，按严重程度排序输出报告
```

### SOP E：Mock 集成测试（支付/权限/设备）

```
wechat_automator(action='mock_wx', method='requestPayment', result_json='{"errMsg":"requestPayment:ok"}')
wechat_automator(action='mock_wx', method='getUserProfile',  result_json='{"userInfo":{"nickName":"测试用户"}}')
wechat_automator(action='mock_wx', method='getLocation',     result_json='{"latitude":23.099,"longitude":113.324}')
wechat_automator(action='tap', selector='.pay-btn')         # 触发交互
wechat_automator(action='page_data')                        # 验证 data 变化
```

> Mock 仅当前会话有效，重启 IDE 后需重新设置。

### SOP F：网络调试与 UI 适配

**① 网络与 API 调试**

```
# 拦截请求（逻辑层注入）
evaluate(expression='var o=wx.request; wx.request=function(p){console.log(p.url);return o.apply(wx,arguments)}')
# 模拟超时
mock_wx(method='request', result_json='{"errMsg":"request:fail timeout"}')
```

**② UI 适配测试**

```
mock_wx(method='getSystemInfo', result_json='{"theme":"dark"}')               # 暗黑模式适配
mock_wx(method='getSystemInfo', result_json='{"platform":"mac","windowWidth":1024}')  # iPad/PC 适配
system_info()                                              # 记录 windowWidth/Height
```

---

## CDP 日志策略

```
concise → 仅 errors + warnings（节省 Token，优先使用）
  ↓ summary.errors > 0 时
full    → 完整日志 + source 定位 → wechat_file(action='read_file', file_path=source)
```

| 场景 | 推荐参数 |
|------|---------|
| 快速诊断 | `duration=5, detail_level='concise', max_logs=20` |
| 深度排查 | `duration=10, detail_level='full', max_logs=100` |
| 页面巡检 | `duration=3, detail_level='concise', max_logs=30` |

---

## 返回值格式

```json
{"success": true,  "data": {...}, "message": "操作描述"}
{"success": false, "error_code": "CLI_TIMEOUT", "message": "...", "hint": "修复提示"}
```

| error_code | 含义 | 处理 |
|-----------|------|------|
| `PARAM_MISSING` | 必填参数缺失 | 查看 hint 字段 |
| `CLI_NOT_FOUND` | 找不到 CLI | 检查 `WECHAT_DEVTOOLS_CLI` |
| `PROJECT_PATH_MISSING` | 项目路径未配置 | 检查 `WECHAT_PROJECT_PATH` |
| `NODE_NOT_FOUND` | Node.js 未安装 | 安装 Node.js ≥ 8.0 |
| `CLI_TIMEOUT` | CLI 执行超时 | 开启服务端口；重启 IDE |

---

## 故障速查

| 症状 | 原因 | 解决 |
|------|------|------|
| CDP 采集失败（9222 无响应） | IDE 未用 cdp_enabled 启动 | `wechat_ide(action='open', cdp_enabled=True)` 重启 |
| 截图空白 / 尺寸 0 | automator 未启动或页面未渲染 | 确认 `start` 已调用；增加 `wait_ms=3000` |
| `Page is not found` | page_path 拼写错 / 未注册 | `wechat_file(action='list_pages')` 核查 |
| `Element is obfuscated` | 元素被遮挡或在 shadow-root 外 | 检查 WXML 结构，尝试父节点 |
| `Cannot find context` | 逻辑层崩溃 / 正在重载 | 等待 3s 后重试 |
| `CLI_TIMEOUT` | 服务端口未开启 / IDE 未运行 | 开启服务端口；`wechat_ide(action='open')` |
| 元素未找到 | 不在当前页面或 selector 错 | `page_stack` 确认页面；`element_info` 验证 selector |

---

## 绝对红线

- ❌ 未确认 `is_login: true` 时调用 `preview` / `upload`
- ❌ 对生产项目调用 `cache_clean(clean_type='all')`
- ❌ 在 `evaluate` 中执行 `eval()` 或不安全代码
- ❌ 脑补运行状态——必须以 MCP 接口返回的实际数据为准
- ❌ 同一失败操作重试超过 3 次（应转为诊断根因）
- ❌ 自动化测试中使用 `sleep` 硬等待（用 `wait_ms` 或轮询 `page_data`）
- ✅ `wechat_screenshot` 必须提供完整绝对路径 `output_path`
- ✅ 使用任何自动化/截图功能前必须先调用 `automator(action='start')`
- ✅ 执行 `tap`/`input` 前先用 `element_info` 确认元素存在
- ✅ `upload` 前确认版本号已递增，`build_npm` 已执行
- ✅ 关注 CDP 日志中的 `[Violation]` 标记（渲染阻塞/性能问题）
