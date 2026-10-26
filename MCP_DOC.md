# MCP 工具箱完整文档 (v0.9.20)

「**瘦 MCP + 胖 Skill**」架构：44 个原子能力聚合为 **7 个工具**，每个工具通过 `action` 参数切换功能子集，覆盖小程序全生命周期。操作流程与排障手册在配套 Skill（`.agents/skills/wechat-devtools/`）里。

> 云函数与云数据库管理请使用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)（`manageFunctions` / `readNoSqlDatabaseContent` 等），无 IDE 依赖且功能更完整。

所有工具返回统一 JSON 信封：

```json
// 成功
{"success": true, "data": {...}, "message": "操作描述"}
// 失败
{"success": false, "error_code": "PARAM_MISSING", "message": "...", "hint": "修复建议"}
```

> [!IMPORTANT]
> **必须手动开启开发者工具的服务端口**：`设置` → `安全设置` → `服务端口` → `开启`。未开启将导致所有 CLI 操作报 `CLI_TIMEOUT`。

---

## 目录

1. [wechat_ide — IDE 生命周期管理](#wechat_ide)
2. [wechat_build — 构建与发布](#wechat_build)
3. [wechat_automator — 自动化交互](#wechat_automator)
4. [wechat_inspector — 运行时日志采集](#wechat_inspector)
5. [wechat_screenshot — 界面截图](#wechat_screenshot)
6. [wechat_navigate — 跳转并采集日志](#wechat_navigate)
7. [wechat_file — 项目文件读取](#wechat_file)
8. [Mock 场景示例](#mock-场景示例)

---

## wechat_ide

IDE 生命周期管理。合并原 `wechat_open`、`wechat_login`、`wechat_is_login`、`wechat_close_project`、`wechat_quit_ide`、`wechat_get_status`。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `open` | 启动 IDE 并打开项目。`cdp_enabled=true`（默认）先检查 `cdp_port` 占用者，再 kill 已运行的 IDE 带 CDP 重启，等小程序 target 就绪后做启动健康检查 | — |
| `login` | 登录，生成二维码供扫码 | — |
| `is_login` | 检查是否已登录 | — |
| `close` | 关闭指定项目窗口 | — |
| `quit` | 退出整个 IDE，等进程真正消失后返回 `exited`（macOS 用 pgrep、Windows 用 tasklist 轮询，上限 10s） | — |
| `status` | 环境诊断：CLI / 项目路径 / Node.js / 服务端口 / CDP 端口占用者 / 项目窗口 / skill 副本版本 / 官方内建 MCP，只读 | — |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言：`en` 或 `zh` |
| `cdp_enabled` | bool | `true` | 是否开启 CDP 调试端口，`open` 时使用 |
| `cdp_port` | int | `WECHAT_CDP_PORT` 或 `9222` | CDP 调试端口。`open` 前检查端口占用者，被别的浏览器占着直接报错；成功后同会话 `wechat_inspector` / `wechat_navigate` / `wechat_build(compile)` 不传即沿用 |
| `qr_format` | string | `terminal` | 二维码格式，`login` 时使用 |
| `qr_output` | string | null | 二维码输出路径，`login` 时使用 |
| `result_output` | string | null | 登录结果输出文件路径，`login` 时使用（透传 CLI `--result-output`） |

**`action='status'` 返回字段**

除 `mcp_version` / `cli_exists` / `project_exists` / `node_available` 外，另返回：

- `service_port_enabled` — 开发者工具「设置 → 安全设置 → 服务端口」的开关状态。**未开启是 `CLI_TIMEOUT` 的头号原因**，为 `false` 时 message 会直接点出。读不到为 `null`（无法判断，非「已关闭」）
- `ide_port` — IDE 当前的服务端口，由 IDE 自己落盘的状态文件读出
- `official_mcp` — 开发者工具 2.x 内建 MCP 服务探测结果：`{available, port, running, sessions}`。
  只做一次只读 `GET http://127.0.0.1:<ide_port>/mcp/heartbeat`，不发 `initialize`（那会在 IDE 侧登记授权客户端）。
  `available: true` 时 message 会提示「基础操作优先用官方工具，本 MCP 专注长图截图 / CDP 日志 / SOP」；
  1.06、IDE 未启动或端口漂移时为 `false`，不报错
- `cdp_port` / `cdp_port_default` / `cdp_port_session` — 当前生效的 CDP 端口（本会话 `open` 过的端口 > `WECHAT_CDP_PORT` > 9222）及其来源
- `cdp_port_occupant` — 生效端口上现在是谁：`{listening, kind, browser, sample, miniprogram_targets}`，`kind` 为 `ide` / `foreign` / `empty` / `none`。
  `foreign`（典型：常驻 Chrome 占着 9222）时 message 提示换端口或设 `WECHAT_CDP_PORT`
- `project_window_open` — 端口上是 IDE 时按小程序 target 数判断项目窗口是否活着；不是 IDE 时为 `null`
- `skill_version` — 项目目录 `.agents/skills/wechat-devtools/SKILL.md` 的版本，读不到为 `null`；与 `mcp_version` 不一致时 message 提示更新 skill 副本

**`action='open'` 返回字段**

- `ide_runtime` — `nwjs`（IDE 1.x）/ `electron`（IDE 2.x）/ `win32`。Windows 也按安装根下
  `code\package.nw`（1.x）/ `resources\app.asar.unpacked`（2.x）判定，判定点照抄官方 wechatide-skill 的
  `install-root.mjs`；`win32` 仅在两者都探测不到时出现，表示沿用旧的「`cli.bat` → `微信开发者工具.exe`」推导
- `cdp_ready` — 仅 IDE 2.x 出现。CDP 端口是否确认在监听。为避免「项目打开了但 CDP 没起来」的假成功，
  2.x 会先等 CDP 端口与 IDE 服务端口双双就绪才继续；任一未就绪直接返回失败（Windows 2.x 的 `.ide` 端口文件可能过期，只要求 CDP 就绪）
- 失败时可能附顶层字段：`cdp_port_occupant`（端口被别的浏览器占着，IDE 未动）、`startup_errors` + `cdp_summary`（启动健康检查发现错误）
- `project_opened` — 仅 IDE 2.x 出现。2.x 不再识别命令行 `--project`，需先带 CDP 起进程再由 CLI 打开项目，此字段表示第二步是否成功
- `miniprogram_targets_ready` — cdp_enabled 时出现。启动健康检查前 8 秒内是否在该 CDP 端口看到小程序 target
  （`__pageframe__` / `appservice`）。为 `false` 时 message 带 ⚠：项目可能没在这个实例里打开（单实例锁竞态）或仍在加载，不判失败

---

## wechat_build

构建与发布。合并原 `wechat_compile_check`、`wechat_preview`、`wechat_upload`、`wechat_build_npm`、`wechat_cache_clean`。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `compile` | **[最常用]** 触发编译，捕获所有 Error 和 Warning。v0.9.0 daemon 自动重连 automator，无需重新 `start` | — |
| `preview` | 生成预览二维码 | — |
| `upload` | 上传代码到微信后台 ⚠️ | **`version`** |
| `build_npm` | 构建 NPM 依赖 | — |
| `cache_clean` | 清除指定类型缓存 | — |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `version` | string | null | 版本号，`upload` 时**必填**，例如 `1.0.0` |
| `desc` | string | null | 版本描述，`upload` 时使用 |
| `qr_format` | string | `base64` | `preview` 二维码格式：`terminal` / `base64` |
| `qr_output` | string | null | 二维码输出文件路径，相对路径相对 `project_path` |
| `info_output` | string | null | 编译/上传信息输出 JSON 路径 |
| `compile_condition` | string | null | 自定义编译条件（JSON 字符串）。注意：对 tabBar 页面可能无效（app 路由守卫覆盖），用 `evaluate` + `wx.reLaunch` 跳转更可靠 |
| `compile_type` | string | null | 编译类型：`miniprogram` 或 `plugin` |
| `clean_type` | string | `compile` | 缓存类型：`storage`、`file`、`compile`、`auth`、`network`、`session`、`all` |
| `port` | int | null | IDE HTTP 服务端口号 |
| `cdp_port` | int | 沿用 `open` 的端口 | CDP 调试端口，`compile` 采集 WXML 运行时错误时使用。不传则沿用本会话 `wechat_ide(open)` 的端口 |
| `lang` | string | null | 界面语言 |

**`action='compile'` 返回字段**

`compiled`、`errors`、`warnings`、`status`、`compile_info`、`wxml_errors`（CDP 采到的 WXML 运行时错误）、`npm_warning`（`miniprogram_npm` 缺失或早于 `node_modules`）、`cdp_skipped`（CDP 端口被别的浏览器占着，本次未采 WXML 运行时错误）、`automator_reconnected` / `automator_verified` / `reconnect_attempts`（默认 9420 在监听时的自动重连结果）。CLI 返回 0 但 stderr 命中端口占用等致命模式时降级为失败并返回 `fatal_errors`。`preview` 另返回 `qr_stale_warning`（二维码文件未更新，bundle 可能没刷新）。

---

## wechat_automator

自动化交互与运行时查询。合并所有原自动化工具（13 个 action）。

> **前提**：需先调用 `wechat_automator(action='start')` 开启 9420 自动化端口，**只需一次**。连接断开时动作会自动 `start` 一次并重试（返回 `auto_recovered`），有副作用的动作只在连接阶段失败时重试。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `start` | 开启自动化端口，TCP 与 WS 两级验证；端口不监听时自动重跑 `cli auto`（最多 3 轮），WS 级按截止时间轮询（默认 45s，`ready_timeout` 可调） | — |
| `tap` | 模拟点击指定元素 | **`selector`** |
| `input` | 向 input/textarea 输入文本 | **`selector`**, **`value`** |
| `element_info` | 获取元素详情（文本/尺寸/位置/WXML） | **`selector`** |
| `set_data` | 热更新页面 data，无需重新编译 | **`data_json`** |
| `call_method` | 调用当前页面的指定方法，返回当前页面路径 | **`method`** |
| `call_wx` | 直接调用 wx 对象上的方法。同步返回的 API（`*Sync`、`create*`、`*Manager`、`getWindowInfo` 等信息类）自动改经 evaluate 直调并返回 `sync: true` | **`method`** |
| `mock_wx` | Mock wx API 的返回值 | **`method`**, **`result_json`** |
| `evaluate` | 在逻辑层执行 JS。推荐 `fn_source` 传完整函数源码（多语句 / `return` 由函数体自决，入参走 `args_json`）；`expression` 仅限单个表达式 | **`fn_source` 或 `expression`** |
| `page_stack` | 获取当前页面栈信息 | — |
| `page_data` | 读取当前活跃页面的 data 状态 | — |
| `system_info` | 获取运行时系统信息 | — |
| `storage` | 获取本地缓存数据（key 为空则列出所有） | — |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `project_path` | string | 环境变量 | 小程序项目路径，`start` 时使用 |
| `ready_timeout` | int | `45` | `start` 等待 automator 首次应答的总秒数，范围 5~180；大项目冷启动可加大 |
| `selector` | string | null | CSS 选择器，例如 `.submit-btn`、`#login` |
| `value` | string | null | 输入值 |
| `style_prop` | string | null | 要查询的 CSS 属性名，`element_info` 时可选 |
| `data_json` | string | null | JSON 数据字符串，例如 `{"key": "val"}` |
| `method` | string | null | 方法名 |
| `args_json` | string | null | JSON 数组字符串：`call_method` / `call_wx` 的方法参数，或 `evaluate` 中 `fn_source` 的函数入参 |
| `fn_source` | string | null | **推荐**。`evaluate` 时与 `expression` 二选一：完整函数源码，如 `function(){ const p = getCurrentPages(); return p.length }` 或 `(a,b)=>a+b`，以 `page.evaluate(fn, ...args)` 执行，返回 `mode: "function"` |
| `expression` | string | null | 单个 JS 表达式（如 `getApp().globalData`）。多语句会退回语句模式（全部执行但无 `return` 则为 `null` 并附 hint），这类需求请改用 `fn_source` |
| `result_json` | string | null | Mock 返回值（JSON 字符串） |
| `key` | string | null | Storage key，为空则列出所有 key |
| `expected_path` | string | null | `page_data` 时可选：期望页面路径，最多轮询 10 次（300ms 间隔）等页面匹配；不匹配返回 `path_mismatch: true` 与 `warning` |
| `auto_account` | string | null | 指定 openid，`start` 时可选 |

---

## wechat_inspector

运行时日志采集。合并原 `wechat_get_console_logs`、`wechat_get_cdp_logs`。

**必填参数**：`action`

| action | 功能 | 采集来源 |
|--------|------|---------|
| `console` | 采集 console 日志和 JS 运行时异常 | automator 端口 |
| `cdp` | 采集底层高清日志（WXML 警告/废弃 API/渲染层报错），能回放采集开始前的缓冲区 | CDP 端口（沿用 `open` 的端口） |

> **cdp 前提**：项目以 `wechat_ide(action='open', cdp_enabled=True)` 打开。端口上若是别的浏览器（`status` 的 `cdp_port_occupant.kind` 为 `foreign`）会直接报错而不是采错日志。

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `console` 或 `cdp` |
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `detail_level` | string | `concise` | `cdp` 时使用：`concise`（仅 errors+warnings）或 `full`（全量） |
| `max_logs` | int | `50` | `cdp` 时使用：最大返回条数，超出时 `truncated=true` |
| `cdp_port` | int | 沿用 `open` 的端口 | CDP 调试端口，不传则沿用本会话 `open` 的端口 |
| `auto_port` | int | `9420` | 自动化端口，`console` 时使用 |
| `log_type` | string | `all` | `console` 时使用：`all`、`console`、`exception` |
| `tap_selector` | string | null | 采集期间自动点击的 CSS 选择器 |
| `tap_delay` | int | `500` | 点击延迟（毫秒） |

**返回值格式（cdp action）**

```json
{
  "success": true,
  "data": {
    "summary": {"total": 5, "errors": 2, "warnings": 1, "info": 2, "truncated": false},
    "logs": [
      {"level": "error", "message": "Cannot read property ...", "source": "pages/index/index", "timestamp": "..."}
    ]
  },
  "message": "采集 10 秒，发现 2 个错误、1 个警告。"
}
```

`source`：渲染层为页面路径，逻辑层统一为 `appservice`，其余为原始 URL。`message` 含 `[object Object]` 时附 `hint`。

**返回值格式（console action）**：`summary{total, errors, warnings, exceptions}`、`console_logs`、`exceptions`、`port`、`duration`；`duration < 6` 且 `log_type` 含异常时附 `duration_warning`（监听器在连接建立后才注册，短采集会漏掉之前的异常）。

---

## wechat_screenshot

捕获当前小程序模拟器的界面截图，默认支持滚动拼接长图，保存为 PNG 文件。

> **前提**：需先调用 `wechat_automator(action='start')` 开启自动化端口（失联会自动 `start` 一次重试）。
>
> **限制**：截图可能无法捕获 fixed/absolute 定位的 overlay（弹窗、蒙层），以 `page_data` 为准；scroll-view 滚动的页面只能截到视口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | string | null | 截图保存路径。留空存到 `<project_path>/screenshots/screenshot_<时间戳>.png`，父目录自动创建 |
| `auto_port` | int | `9420` | 自动化端口 |
| `overlap` | int | `50` | 分段重叠像素数，防止内容截断；出现 `content_gaps` 时调大（如 150） |
| `full_page` | bool | `true` | 长图拼接；`false` 只截当前视口 |
| `scroll_top` | int | null | 截图前滚动到的位置（逻辑像素），配合 `full_page=false` 分段截 |
| `page_path` | string | null | 当前页不匹配时先跳转到该页（tabBar 页走 `switchTab`，其余 `navigateTo`） |

**返回字段**：`path`、`width`、`height`、`segments`、`file_size`、`fixed_header` / `fixed_footer`（识别到的固定区高度，物理像素）。拼接不完整时追加诊断字段且 message 带 ⚠：`is_scroll_view_page: true`（只截到视口）、`truncated: true`（超分段上限，底部没拍到）、`content_gaps: N`（N 处内容丢失）、`detection_confident: false`（固定头尾识别不可靠）。automator 失联自动恢复后附 `auto_recovered`。

---

## wechat_navigate

跳转到指定页面，等待指定时间，同步采集 CDP 高清日志。适合检查页面初始化（`onLoad`、`onShow`）阶段的错误。

> **前提**：需先调用 `wechat_automator(action='start')` 并以 `cdp_enabled=True` 打开项目。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 要跳转的页面路径，例如 `pages/index/index` |
| `wait_ms` | int | `2000` | 跳转后等待时间（毫秒），范围 100~30000 |
| `timeout` | int | `30` | 总超时时间（秒），范围 10~120。实际生效值 = max(timeout, wait_ms/1000 + 10)，调大 `wait_ms` 不会撞到该超时 |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `cdp_port` | int | 沿用 `open` 的端口 | CDP 调试端口，不传则沿用本会话 `open` 的端口 |
| `detail_level` | string | `concise` | `concise`（仅 errors+warnings）或 `full` |
| `clear_logs` | bool | `true` | 是否过滤跳转前的 CDP 历史日志（基于时间戳）。设为 `false` 可获取完整累积日志。 |
| `check_data` | bool | `true` | 跳转后检查 page_data，如超过 70% 字段为空且 URL 含 query 参数，追加参数名错误警告。 |
| `max_logs` | int | `50` | 最大返回 CDP 日志条数 |
| `project_path` | string | 环境变量 | 用于读 app.json 判断 tabBar 页（tabBar 页走 `switchTab`，其余 `reLaunch`） |

**返回字段**：`page`、`wait_ms`、`navigation_method`（`switchTab` / `reLaunch`）、`cdp_available`、`current_page{path, query}`、`cdp_logs{summary, logs}`、`logs_since`、`filtered_before_navigation`。跳转后路径不匹配加 `navigation_mismatch: true`；疑似 query 参数名错误加 `warning`；CDP 端口被别的浏览器占着时不采日志并加 `cdp_warning`；automator 失联自动恢复后附 `auto_recovered`。

---

## wechat_file

项目文件读取。合并原 `wechat_project_info`、`wechat_list_pages`、`wechat_read_page`、`wechat_read_file`。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `project_info` | 获取项目完整信息（config/app.json/目录结构） | — |
| `list_pages` | 列出 app.json 中所有注册页面，检查文件完整性 | — |
| `read_page` | 读取指定页面全部源码（.wxml/.wxss/.js/.json） | **`page_path`** |
| `read_file` | 读取项目中任意单个文件，最多 800 行 | **`file_path`** |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `page_path` | string | null | 页面路径，`read_page` 时必填，例如 `pages/index/index` |
| `file_path` | string | null | 相对文件路径，`read_file` 时必填，例如 `app.json` |

**路径解析规则**

`read_page` / `read_file` 与 `list_pages` / `project_info` 口径一致：先按 `project.config.json` 的
`miniprogramRoot` 解析，再回退项目根（普通项目两者相同）。因此云开发项目里 `list_pages` 返回的
`pages/home/index` 可直接喂给 `read_page`，`app.json` 也能被 `read_file` 读到。

- `read_page` 返回 `resolved_base`（实际命中的根目录）
- `read_file` 返回 `resolved_path`；同名文件在多个根下都存在时额外返回 `also_found_at`
- 例外：`project.config.json` / `project.private.config.json` 优先取项目根那份（云开发项目的
  `miniprogram/` 下可能有内容不同的非权威副本）

---

## Mock 场景示例

通过 `wechat_automator(action='mock_wx', method='...', result_json='...')` 覆盖 `wx` API 返回值，无需真实设备权限或支付环境。

> **注意**：Mock 仅在当前自动化会话中有效，重启开发者工具后需重新设置。

### 场景一：支付成功

```json
{
  "tool": "wechat_automator",
  "arguments": {
    "action": "mock_wx",
    "method": "requestPayment",
    "result_json": "{\"errMsg\": \"requestPayment:ok\"}"
  }
}
```

### 场景二：弹窗确认（showModal）

```json
{
  "tool": "wechat_automator",
  "arguments": {
    "action": "mock_wx",
    "method": "showModal",
    "result_json": "{\"confirm\": true, \"cancel\": false, \"errMsg\": \"showModal:ok\"}"
  }
}
```

### 场景三：定位授权（chooseLocation）

```json
{
  "tool": "wechat_automator",
  "arguments": {
    "action": "mock_wx",
    "method": "chooseLocation",
    "result_json": "{\"name\": \"腾讯北京总部\", \"address\": \"北京市海淀区科学院南路2号\", \"latitude\": 39.9842, \"longitude\": 116.3093, \"errMsg\": \"chooseLocation:ok\"}"
  }
}
```

### 场景四：相册选择（chooseImage）

```json
{
  "tool": "wechat_automator",
  "arguments": {
    "action": "mock_wx",
    "method": "chooseImage",
    "result_json": "{\"tempFilePaths\": [\"wxfile://tmp_photo_001.jpg\"], \"tempFiles\": [{\"path\": \"wxfile://tmp_photo_001.jpg\", \"size\": 102400}], \"errMsg\": \"chooseImage:ok\"}"
  }
}
```

### 场景五：获取用户信息（getUserProfile）

```json
{
  "tool": "wechat_automator",
  "arguments": {
    "action": "mock_wx",
    "method": "getUserProfile",
    "result_json": "{\"userInfo\": {\"nickName\": \"测试用户\", \"avatarUrl\": \"https://example.com/avatar.png\", \"gender\": 1}, \"errMsg\": \"getUserProfile:ok\"}"
  }
}
```

---

*返回 [README](./README.md)*
