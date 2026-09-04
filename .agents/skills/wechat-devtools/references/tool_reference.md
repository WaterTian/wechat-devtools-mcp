# wechat-devtools-mcp 工具参数完整参考 (v0.9.18)

> `SKILL.md` 的扩展参考：7 个聚合工具的全部参数、action 与返回字段，均对照源码核对。SOP 流程见 `SKILL.md`。

统一返回信封：

```json
{"success": true,  "data": {...}, "message": "操作描述"}
{"success": false, "error_code": "PARAM_MISSING", "message": "...", "hint": "修复建议"}
```

失败时可能追加顶层字段（如 `open` 的 `startup_errors`、`compile` 的 `fatal_errors`）。`error_code` 见 [第 8 节](#8-错误码速查表)。

> 必须开启开发者工具服务端口：`设置 → 安全设置 → 服务端口`。未开启则所有 CLI 操作报 `CLI_TIMEOUT`。

## 目录

1. [wechat_ide](#1-wechat_ide)
2. [wechat_build](#2-wechat_build)
3. [wechat_automator](#3-wechat_automator)
4. [wechat_inspector](#4-wechat_inspector)
5. [wechat_screenshot](#5-wechat_screenshot)
6. [wechat_navigate](#6-wechat_navigate)
7. [wechat_file](#7-wechat_file)
8. [错误码速查表](#8-错误码速查表)

云函数 / 云数据库请用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)，本 MCP 不提供云开发工具。

---

## 1. wechat_ide

IDE 生命周期管理。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | 必填 | `open` / `login` / `is_login` / `close` / `quit` / `status` |
| `project_path` | string | `WECHAT_PROJECT_PATH` | 项目根目录绝对路径，`open` / `close` 使用 |
| `appid` | string | null | 覆盖 project.config.json 的 AppID，`open`（`cdp_enabled=false`）时透传 CLI |
| `port` | int | null | IDE HTTP 服务端口，多实例时使用 |
| `lang` | string | null | 界面语言 `en` / `zh` |
| `cdp_enabled` | bool | `true` | `open` 时是否带 CDP 调试端口启动 |
| `cdp_port` | int | `9222` | CDP 端口。被 Chrome 等占用时换一个，须与 `wechat_inspector` / `wechat_navigate` / `wechat_build(compile)` 一致 |
| `qr_format` | string | `terminal` | `login` 二维码格式：`terminal` / `image` / `base64` |
| `qr_output` | string | null | `login` 二维码输出文件 |
| `result_output` | string | null | `login` 结果输出文件（透传 CLI `--result-output`） |

### action 说明

| action | 行为 | 返回 `data` |
|--------|------|-------------|
| `open` | `cdp_enabled=true`：kill 已运行的 IDE，带 `--remote-debugging-port` 重启。IDE 2.x 为两步式：等 CDP 端口与 IDE 服务端口都监听后再由 CLI 打开项目（1.x 直接透传 `--project`）。随后等小程序 target 出现，采集 3 秒 CDP 日志做启动健康检查，有 error 即返回 `success:false` + `startup_errors` + `cdp_summary`。`cdp_enabled=false`：只执行 `cli open`，不重启 IDE | `cdp_enabled`、`cdp_port`、`ide_runtime`（`nwjs` / `electron` / `win32`，`win32` 表示 Windows 两个布局探测点都不存在、沿用旧推导）、`cdp_ready`、`project_opened`（后两者仅 2.x）、`miniprogram_targets_ready`（`false` 时 message 带 ⚠：项目可能没在带 CDP 的实例里打开，先 `start` 试探、不行重试 `open`） |
| `login` | 生成登录二维码，需手机扫码 | `stdout` |
| `is_login` | 查登录态 | `logged_in`、`stdout` |
| `close` | 关闭项目窗口，不退出 IDE | `{}` |
| `quit` | 退出 IDE 进程，并等进程真正消失（macOS pgrep / Windows tasklist 轮询，上限 10s） | `exited: true/false`（判断不了时为 `null`） |
| `status` | 环境诊断，只读 | 见下例 |

### `status` 返回示例

```json
{
  "success": true,
  "data": {
    "mcp_version": "0.9.18",
    "cli_path": "/Applications/wechatwebdevtools.app/Contents/MacOS/cli",
    "cli_exists": true,
    "project_path": "/Users/me/Projects/mini-app",
    "project_exists": true,
    "node_available": true,
    "node_path": "/opt/homebrew/bin/node",
    "service_port_enabled": true,
    "ide_port": 11071,
    "official_mcp": {"available": true, "port": 11071, "running": true, "sessions": 0},
    "project_name": "mini-app",
    "appid": "wx1234567890",
    "lib_version": "3.8.0"
  },
  "message": "状态正常。检测到开发者工具内建 MCP 服务（2.x，端口 11071）：……"
}
```

- `service_port_enabled`：读 IDE 落盘的状态文件，`null` 表示读不到，不等于关闭。
- `official_mcp`：对 `http://127.0.0.1:<ide_port>/mcp/heartbeat` 做一次只读探测，不发 `initialize`。1.06、IDE 未启动或端口漂移时 `available: false`。
- `project_name` / `appid` / `lib_version` 仅在项目目录存在且有 project.config.json 时出现。

---

## 2. wechat_build

构建与发布。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | 必填 | `compile` / `preview` / `upload` / `build_npm` / `cache_clean` |
| `project_path` | string | `WECHAT_PROJECT_PATH` | 项目根目录 |
| `version` | string | null | `upload` 必填，如 `1.0.0` |
| `desc` | string | null | `upload` 版本描述 |
| `qr_format` | string | `base64` | `preview` 二维码格式：`terminal` / `base64` |
| `qr_output` | string | null | `preview` 二维码文件。相对路径相对 `project_path` 解析，父目录自动创建 |
| `info_output` | string | null | `preview` 编译信息 JSON 文件，解析规则同上 |
| `compile_condition` | string | null | `preview` 自定义编译条件（JSON 字符串）。对 tabBar 页可能被路由守卫覆盖 |
| `compile_type` | string | null | `miniprogram` / `plugin` |
| `clean_type` | string | `compile` | `cache_clean` 类型：`storage` / `file` / `compile` / `auth` / `network` / `session` / `all` |
| `cdp_port` | int | `9222` | `compile` 采集 WXML 运行时错误用。须与 `wechat_ide(open)` 一致，否则 `wxml_errors` 恒为空 |
| `port` | int | null | IDE HTTP 服务端口 |
| `lang` | string | null | 界面语言 |

### action 说明

| action | 行为 | 返回 `data` |
|--------|------|-------------|
| `compile` | 触发编译，按行分类 stderr 为 errors / warnings / status（进度指示与 Node 弃用提示已跳过）；再采集 3 秒 CDP 提取 `wxml_errors`；成功后若默认端口 9420 在监听，则清掉 daemon 旧连接并做 WS 级健康检查。CLI 返回 0 但 stderr 命中端口占用等致命模式时降级为失败并返回 `fatal_errors` | `compiled`、`errors`、`warnings`、`status`、`compile_info`、`project`、`wxml_errors`、`npm_warning`（miniprogram_npm 缺失或早于 node_modules）、`automator_reconnected`、`automator_verified`、`reconnect_error`、`port_changed`、`old_port`、`new_port` |
| `preview` | 生成预览二维码，需已登录 | `stdout`、`qr_output`、`qr_output_mtime`、`qr_stale_warning`（二维码文件 mtime 未变，bundle 可能没刷新）、`info_output` |
| `upload` | 上传到微信后台，生产操作 | `version`、`stdout` |
| `build_npm` | 构建 npm 依赖。新增或更新依赖后必须执行 | `{}` |
| `cache_clean` | 清缓存，`all` 慎用 | `clean_type` |

### `compile` 返回示例

```json
{
  "success": true,
  "data": {
    "compiled": true,
    "errors": [],
    "warnings": ["pages/index/index.wxml: 属性 wx:key 应使用唯一标识符"],
    "status": ["✓ compile success"],
    "compile_info": {},
    "project": "/Users/me/Projects/mini-app",
    "wxml_errors": [],
    "automator_reconnected": true,
    "automator_verified": true,
    "port_changed": false
  },
  "message": "编译成功。 automator 已自动重连并验证就绪。"
}
```

自动重连只针对默认 9420。用了非默认 `auto_port` 的话 compile 后自行调一次 `start`。

---

## 3. wechat_automator

自动化交互与运行时查询，13 个 action。先调 `start` 开启自动化端口，整个会话一次。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | 必填 | 见下表 |
| `auto_port` | int | `9420` | 自动化端口 |
| `project_path` | string | `WECHAT_PROJECT_PATH` | `start` 使用 |
| `auto_account` | string | null | `start` 指定测试账号 openid |
| `selector` | string | null | CSS 选择器，`tap` / `input` / `element_info` 必填 |
| `value` | string | null | `input` 必填 |
| `style_prop` | string | null | `element_info` 可选，取指定 CSS 属性 |
| `data_json` | string | null | `set_data` 必填，JSON 对象字符串 |
| `method` | string | null | `call_method` / `call_wx` / `mock_wx` 必填 |
| `args_json` | string | null | JSON 数组：`call_method` / `call_wx` 的参数，或 `evaluate(fn_source)` 的入参 |
| `result_json` | string | null | `mock_wx` 必填，Mock 返回值 JSON |
| `fn_source` | string | null | `evaluate` 推荐入口：完整函数源码 |
| `expression` | string | null | `evaluate` 兼容入口：单个表达式。与 `fn_source` 二选一，同时给以 `fn_source` 为准 |
| `key` | string | null | `storage` 指定 key，不传列出全部 |
| `expected_path` | string | null | `page_data` 期望页面路径，传入后最多轮询 10 次（300ms 间隔）等页面匹配 |

### action 说明

| action | 行为 | 返回 `data` |
|--------|------|-------------|
| `start` | 执行 `cli auto`，再做 TCP 与 WS 两级验证。端口不监听时重跑 `cli auto`（最多 3 轮，间隔 3s；纯 CLI open 后窗口未加载完会假成功）；WS 失败会清缓存退避 2 秒重试一次 | 就绪：`port`、`verified: true`、`tcp_ready`、`ws_ready`、`verify_attempts`、`cli_attempts`。未就绪：`verified: false`、`retry_after_ms: 3000`、`hint`。3 轮后端口仍不监听则失败并附恢复 hint |
| `tap` | 点击元素 | `selector` |
| `input` | 输入文本 | `selector`、`value` |
| `element_info` | 元素信息 | `element{tagName, text, wxml, size, offset, style?}` |
| `set_data` | 热更新当前页 data，无需重编译 | `path`、`updated_keys` |
| `call_method` | 调用当前页方法 | `method`、`return_value`、`path`。失败时 message 附当前页面路径 |
| `call_wx` | 调用 `wx.<method>` | `method`、`return_value` |
| `mock_wx` | Mock `wx.<method>` 返回值，当前会话有效 | `method` |
| `evaluate` | 逻辑层执行 JS | `result`、`mode`、`hint?` |
| `page_stack` | 页面栈 | `depth`、`pages` |
| `page_data` | 当前页 data | `path`、`data`；不匹配 `expected_path` 时加 `path_mismatch: true`、`warning` |
| `system_info` | `wx.getSystemInfo` 等价 | `system_info` |
| `storage` | 本地缓存 | 传 `key`：`key`、`value`；不传：`keys`、`current_size`、`limit_size` |

### `evaluate` 说明

推荐 `fn_source`，与官方 `automation_evaluate(fnSource, args)` 同构。函数在小程序 AppService 内以 `page.evaluate(fn, ...args)` 执行，函数体写几条语句、要不要 `return` 都由调用方决定：

```json
{"action": "evaluate",
 "fn_source": "function(url){ const p = getCurrentPages(); wx.reLaunch({url}); return p.length }",
 "args_json": "[\"/pages/index/index\"]"}
```

`expression` 只传单个表达式，如 `getApp().globalData.userInfo`。多语句会退回语句模式（全部执行），没有 `return` 时 `result` 为 `null` 并附 `hint`；字符串字面量里的分号不受影响。

`mode` 取值：`function`（fn_source）/ `expression`（单表达式）/ `statement`（退回语句模式）。

### `mock_wx` 常用模板

| 场景 | method | result_json |
|------|--------|-------------|
| 支付成功 | `requestPayment` | `{"errMsg":"requestPayment:ok"}` |
| 弹窗确认 | `showModal` | `{"confirm":true,"cancel":false,"errMsg":"showModal:ok"}` |
| 定位 | `getLocation` | `{"latitude":23.1,"longitude":113.3,"errMsg":"getLocation:ok"}` |
| 用户信息 | `getUserProfile` | `{"userInfo":{"nickName":"测试用户"},"errMsg":"getUserProfile:ok"}` |
| 网络超时 | `request` | `{"errMsg":"request:fail timeout"}` |

---

## 4. wechat_inspector

运行时日志采集。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | 必填 | `cdp` / `console` |
| `duration` | int | `10` | 采集秒数，1~120 |
| `cdp_port` | int | `9222` | `cdp` 用 |
| `detail_level` | string | `concise` | `cdp` 用：`concise` 只回 errors + warnings，`full` 全量 |
| `max_logs` | int | `50` | `cdp` 用，1~500，超出 `summary.truncated: true` |
| `auto_port` | int | `9420` | `console` 用 |
| `log_type` | string | `all` | `console` 用：`all` / `console` / `exception` |
| `tap_selector` | string | null | `console` 采集期间自动点击的元素 |
| `tap_delay` | int | `500` | 点击延迟毫秒 |

### action 说明

| action | 来源 | 特点 | 返回 `data` |
|--------|------|------|-------------|
| `cdp` | CDP 端口，连接 pageframe（渲染层）与 appservice（逻辑层）target | `Console.enable` 会回放缓冲区，采集开始前的消息也能拿到。已过滤 `[system]`、`WAService.js`、`WAWebview.js` 与 IDE 外壳页；同级别同文本去重 | `summary{total, errors, warnings, info, truncated}`、`logs[{level, message, source, timestamp, hint?}]` |
| `console` | automator 端口事件监听 | 只收连接建立后的事件。`duration < 6` 且 `log_type` 含异常时返回 `duration_warning` | `summary{total, errors, warnings, exceptions}`、`console_logs`、`exceptions`、`port`、`duration` |

### `cdp` 返回示例

```json
{
  "success": true,
  "data": {
    "summary": {"total": 15, "errors": 2, "warnings": 5, "info": 8, "truncated": false},
    "logs": [
      {"level": "error", "message": "Component is not found in path \"components/foo/foo\"", "source": "pages/index/index", "timestamp": "2026-09-03T10:00:01.234Z"},
      {"level": "warning", "message": "无效的 app.json [\"sharePolicy\"]", "source": "ide:///extensions/inject/documentstart/index.js", "timestamp": "2026-09-03T10:00:01.567Z"}
    ]
  },
  "message": "采集 10 秒，发现 2 个错误、5 个警告。"
}
```

`source`：渲染层为页面路径，逻辑层统一为 `appservice`，其余为原始 URL。`message` 含 `[object Object]` 时附 `hint` 建议改用 `evaluate` 取完整返回值。

---

## 5. wechat_screenshot

模拟器截图，默认滚动拼接长图，保存为 PNG。前提：已 `start`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | string | null | 留空存到 `<project_path>/screenshots/screenshot_<时间戳>.png`，父目录自动创建 |
| `auto_port` | int | `9420` | 自动化端口 |
| `overlap` | int | `50` | 分段重叠像素 |
| `full_page` | bool | `true` | `false` 只截当前视口 |
| `scroll_top` | int | null | 截图前滚动到的逻辑像素位置，配合 `full_page=false` |
| `page_path` | string | null | 当前页不匹配时先跳转 |

### 返回示例

```json
{
  "success": true,
  "data": {
    "path": "/Users/me/Projects/mini-app/screenshots/screenshot_20260903_230000.png",
    "width": 724,
    "height": 3004,
    "segments": 3,
    "file_size": 1271144,
    "fixed_header": 12,
    "fixed_footer": 155
  },
  "message": "截图成功，共 3 段，已保存至 …。"
}
```

拼接质量诊断字段只在异常时出现，且 `message` 会带 ⚠：`is_scroll_view_page: true`（只截到视口）、`truncated: true`（底部没拍到）、`content_gaps: N`（N 处内容丢失，增大 `overlap`）、`detection_confident: false`（固定头尾识别不可靠）。`fixed_header` / `fixed_footer` 为识别到的固定区高度（物理像素）。

跳转失败等 JS 侧错误会带 `hint`（如「末尾可能需要 /index」）。fixed / absolute 弹窗蒙层可能拍不到。

---

## 6. wechat_navigate

跳转到指定页面并同步采集 CDP 日志，适合查 `onLoad` / `onShow` 阶段错误。前提：已 `start`，且项目以 `cdp_enabled=true` 打开。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | 必填 | 如 `pages/index/index?id=1`，前导 `/` 可省 |
| `wait_ms` | int | `2000` | 跳转后等待毫秒，100~30000 |
| `timeout` | int | `30` | 总超时秒，10~120。实际取 `max(timeout, wait_ms/1000 + 10)` |
| `auto_port` | int | `9420` | 自动化端口 |
| `cdp_port` | int | `9222` | CDP 端口 |
| `detail_level` | string | `concise` | `concise` / `full` |
| `max_logs` | int | `50` | 最大日志条数 |
| `clear_logs` | bool | `true` | 按时间戳过滤跳转前的历史日志 |
| `check_data` | bool | `true` | 带 query 时检查 page_data，超过 70% 字段为空则给 `warning` |
| `project_path` | string | `WECHAT_PROJECT_PATH` | 用于读 app.json 判断 tabBar 页 |

等待时间建议：静态页 1000~2000，含网络请求 3000~5000，含动画或懒加载 5000+。

### 返回示例

```json
{
  "success": true,
  "data": {
    "page": "/pages/detail/detail?id=1",
    "wait_ms": 3000,
    "navigation_method": "reLaunch",
    "cdp_available": true,
    "current_page": {"path": "pages/detail/detail", "query": {"id": "1"}},
    "cdp_logs": {"summary": {"total": 3, "errors": 0, "warnings": 2, "info": 1, "truncated": false}, "logs": []},
    "logs_since": "2026-09-03T10:30:00.000Z",
    "filtered_before_navigation": 232
  },
  "message": "已跳转至 /pages/detail/detail?id=1，发现 0 个错误、2 个警告。（已过滤 232 条历史日志）"
}
```

- `navigation_method`：tabBar 页为 `switchTab`，其余 `reLaunch`。reLaunch 进入的页面云函数调用可能丢上下文，非 tabBar 页优先 `evaluate` + `wx.navigateTo`。
- 跳转后路径不匹配时加 `navigation_mismatch: true`，`message` 给出手动跳转建议。
- 疑似 query 参数名错误时加 `warning`。

---

## 7. wechat_file

项目文件读取。路径口径统一：先按 `project.config.json` 的 `miniprogramRoot` 解析，再回退项目根。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | 必填 | `project_info` / `list_pages` / `read_page` / `read_file` |
| `project_path` | string | `WECHAT_PROJECT_PATH` | 项目根目录 |
| `page_path` | string | null | `read_page` 必填，如 `pages/index/index` |
| `file_path` | string | null | `read_file` 必填，相对路径，如 `app.json` |

### action 说明

| action | 行为 | 返回 `data` |
|--------|------|-------------|
| `project_info` | 读 project.config.json、app.json、app.wxss（前 100 行）、app.js（前 50 行）与项目根一层目录 | `project_path`、`project_config`、`app_config`、`app.wxss`、`app.js`、`directory[{name, type, size 或 children}]`；解析失败给 `project_config_error` / `app_config_error` |
| `list_pages` | app.json 全部页面并检查四件套是否齐全 | `pages[{path, complete, files[{ext, size}], missing}]`、`total` |
| `read_page` | 读页面 wxml / wxss / js / json | `page_path`、`files{文件名: 内容}`、`resolved_base`（云开发项目为 `<proj>/miniprogram`） |
| `read_file` | 读任意文件，最多 800 行 | `file_path`、`resolved_path`、`total_lines`、`content`、`truncated`、`also_found_at`（同名文件在多个根下都有时列出未采用的） |

`project.config.json` / `project.private.config.json` 固定优先取项目根那份。`list_pages` 返回的 `path` 可直接喂给 `read_page`。

---

## 8. 错误码速查表

`error_code` 只有以下 6 种。连接失败、跳转失败、CLI 非零退出等一律 `UNKNOWN_ERROR`，具体原因看 `message` 与 `hint`。

| error_code | 含义 | 处理 |
|------------|------|------|
| `PARAM_MISSING` | 必填参数缺失（如 `selector`、`version`、`evaluate` 缺 `fn_source` / `expression`） | 按 `hint` 补参数 |
| `CLI_NOT_FOUND` | 找不到开发者工具 CLI 或 IDE 主程序 | 检查 `WECHAT_DEVTOOLS_CLI` |
| `PROJECT_PATH_MISSING` | 项目路径未配置 | 配置 `WECHAT_PROJECT_PATH` 或传 `project_path` |
| `NODE_NOT_FOUND` | Node.js 不可用 | 安装 Node.js 并加入 PATH |
| `CLI_TIMEOUT` | CLI 超时（默认 30 秒） | 开启服务端口；`wechat_ide(action='open')` |
| `UNKNOWN_ERROR` | 其余全部 | 看 `message` / `hint`，参考 `SKILL.md` 故障速查 |

*返回 [SKILL.md](../SKILL.md)*
