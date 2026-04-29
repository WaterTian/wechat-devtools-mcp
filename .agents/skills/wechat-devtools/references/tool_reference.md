# wechat-devtools-mcp 工具参数完整参考 (v0.9.6)

> 本文档是 `SKILL.md` 的扩展参考，提供 7 个聚合 API 的所有参数完整说明（v0.9.5 起 `wechat_cloud` 已禁用）。  
> 基础 SOP 流程请参阅 `SKILL.md`。

所有工具返回统一 JSON 信封：

```json
// 成功
{"success": true, "data": {...}, "message": "操作描述"}
// 失败
{"success": false, "error_code": "PARAM_MISSING", "message": "...", "hint": "修复建议"}
```

> [!IMPORTANT]
> **必须手动开启开发者工具的服务端口**：`设置` → `安全` → `服务端口` → `开启`。未开启将导致所有 CLI 操作报 `CLI_TIMEOUT`。


---

## 目录

1. [wechat_ide — IDE 生命周期管理](#1-wechat_ide)
2. [wechat_build — 构建与发布](#2-wechat_build)
3. [wechat_automator — 自动化交互](#3-wechat_automator)
4. [wechat_inspector — 运行时日志采集](#4-wechat_inspector)
5. [wechat_screenshot — 界面截图](#5-wechat_screenshot)
6. [wechat_navigate — 跳转并采集日志](#6-wechat_navigate)
7. [wechat_file — 项目文件读取](#7-wechat_file)
8. [错误码速查表](#8-错误码速查表)

> 云函数/云数据库管理请改用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)，无 IDE 依赖且能力更完整。

---

## 1. wechat_ide

IDE 生命周期管理。覆盖原 `wechat_open`、`wechat_login`、`wechat_is_login`、`wechat_close_project`、`wechat_quit_ide`、`wechat_get_status`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `open` / `login` / `is_login` / `close` / `quit` / `status` |
| `project_path` | string | 环境变量 | 小程序项目绝对路径，不填则使用 `WECHAT_PROJECT_PATH` |
| `appid` | string | null | 小程序 AppID（`open` 时可选，覆盖 project.config.json 中的值） |
| `port` | int | null | IDE HTTP 服务端口号（多 IDE 实例时使用） |
| `lang` | string | null | 界面语言：`en` 或 `zh` |
| `cdp_enabled` | bool | `true` | 是否开启 CDP 调试端口 9222，`open` 时使用 |
| `qr_format` | string | `terminal` | 二维码格式：`terminal`（终端文字画）或 `base64`，`login` 时使用 |
| `qr_output` | string | null | 二维码输出文件路径（PNG），`login` 时使用 |

### action 说明

| action | 功能描述 | 条件参数 | 注意事项 |
|--------|----------|----------|----------|
| `open` | 打开 IDE 并载入项目，自动触发编译 | `cdp_enabled=true` | 若 IDE 已运行会 kill 并重启，确保 CDP 端口绑定 |
| `login` | 生成登录二维码 | `qr_format`, `qr_output` | 需用户手机扫码，终端输出文字二维码 |
| `is_login` | 检查当前登录状态 | 无 | 返回 `data.logged_in: bool` |
| `close` | 关闭指定项目窗口 | `project_path` | 不退出 IDE 进程 |
| `quit` | 完全退出 IDE 进程 | 无 | ⚠️ 会终止所有项目 |
| `status` | 环境全面诊断 | 无 | 返回 `mcp_version`、CLI 路径、Node.js、项目路径等状态 |

### 返回示例（status action）

```json
{
  "success": true,
  "data": {
    "mcp_version": "0.9.3",
    "cli_exists": true,
    "cli_path": "C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat",
    "project_exists": true,
    "project_path": "D:\\MyProject",
    "node_available": true,
    "node_path": "node (v22.19.0)"
  },
  "message": "状态正常"
}
```

---

## 2. wechat_build

构建与发布。覆盖原 `wechat_compile_check`、`wechat_preview`、`wechat_upload`、`wechat_build_npm`、`wechat_cache_clean`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `compile` / `preview` / `upload` / `build_npm` / `cache_clean` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `version` | string | null | 版本号，`upload` 时**必填**，例如 `1.0.0` |
| `desc` | string | null | 版本描述，`upload` 时使用 |
| `qr_format` | string | `base64` | 二维码格式：`terminal` 或 `base64` |
| `qr_output` | string | null | 二维码保存路径 |
| `info_output` | string | null | 编译/上传信息写入的 JSON 文件路径 |
| `compile_condition` | string | null | 自定义编译条件（JSON 字符串）。注意：对 tabBar 页面可能无效（app 路由守卫覆盖），用 `evaluate` + `wx.reLaunch` 更可靠 |
| `compile_type` | string | null | 编译类型：`miniprogram` 或 `plugin` |
| `clean_type` | string | `compile` | `cache_clean` 时的缓存类型：`storage` / `file` / `compile` / `auth` / `network` / `session` / `all` |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

### action 说明

| action | 功能描述 | 条件必填 | 注意事项 |
|--------|----------|----------|----------|
| `compile` | 触发编译并捕获所有 Error/Warning | 无 | **最常用**；v0.9.0 daemon 自动重连 automator，无需重新 `start` |
| `preview` | 生成预览二维码 | 无 | 需已登录；手机扫码可预览 |
| `upload` | 上传代码到微信后台 | **`version`** | ⚠️ 生产操作，执行前确认代码无误 |
| `build_npm` | 构建 NPM 依赖 | 无 | 新增/更新 npm 包后必须执行 |
| `cache_clean` | 清除缓存 | 无 | 默认清编译缓存；`all` 会清除所有，**小心使用** |

### 返回示例（compile action）

```json
{
  "success": true,
  "data": {
    "errors": [],
    "warnings": ["pages/index/index.wxml: 属性 wx:key 应使用唯一标识符"],
    "compile_time_ms": 1234,
    "automator_reconnected": true,
    "automator_verified": true,
    "port_changed": false,
    "old_port": 9420,
    "new_port": 9420
  },
  "message": "编译完成，0 个错误，1 个警告"
}
```

---

## 3. wechat_automator

自动化交互与运行时查询。覆盖所有原自动化工具（13 个 action）。

> **前提**：需先调用 `wechat_automator(action='start')` 开启 9420 自动化端口，**整个会话只调用一次**。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | 见下表 13 个 action |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `project_path` | string | 环境变量 | 项目路径，`start` 时使用 |
| `selector` | string | null | CSS 选择器，例如 `.submit-btn`、`#login`；`tap`/`input`/`element_info` 时**必填** |
| `value` | string | null | 输入值，`input` 时**必填** |
| `style_prop` | string | null | CSS 属性名，`element_info` 时可选 |
| `data_json` | string | null | JSON 数据字符串，`set_data` 时**必填**，例如 `{"key": "val"}` |
| `method` | string | null | 方法名，`call_method`/`call_wx`/`mock_wx` 时**必填** |
| `args_json` | string | null | 方法参数（JSON 数组字符串），例如 `[1, "hello"]` |
| `expression` | string | null | JS 代码（支持表达式和声明语句），`evaluate` 时**必填** |
| `result_json` | string | null | Mock 返回值（JSON 字符串），`mock_wx` 时**必填** |
| `key` | string | null | Storage key，`storage` 时可选（空=列出全部） |
| `auto_account` | string | null | 指定 openid（测试账号），`start` 时可选 |

### action 详细说明

#### `start` — 开启自动化端口（含连接验证）

```json
{
  "tool": "wechat_automator",
  "arguments": {"action": "start", "project_path": "D:\\MyProject"}
}
```

启动持久化 Node daemon 并开启自动化端口，自动轮询验证连接（最多 10 秒）。返回 `data.verified: true` 表示连接就绪；`verified: false` 表示已启动但未确认连接，此时额外返回 `hint`（操作建议）、`attempts_made`（已尝试次数）、`max_wait_seconds`（最大等待时间）。v0.9.0 起 compile 后 daemon 自动重连，无需再次调用 start。

#### `tap` — 点击元素

```json
{"action": "tap", "selector": ".submit-btn"}
```

#### `input` — 输入文本

```json
{"action": "input", "selector": "input.search-box", "value": "搜索关键词"}
```

#### `element_info` — 获取元素详情

```json
{"action": "element_info", "selector": ".card-item", "style_prop": "color"}
```

返回：元素文本内容、包围盒（x/y/width/height）、WXML 结构、指定 CSS 值。

#### `set_data` — 热更新页面 data

```json
{"action": "set_data", "data_json": "{\"list\": [], \"loading\": false, \"title\": \"测试\"}"}
```

修改立即生效，无需重编译。适合快速验证 UI 状态切换。

#### `call_method` — 调用页面方法

```json
{"action": "call_method", "method": "onRefresh", "args_json": "[]"}
```

返回 `data.path` 标识当前页面路径；失败时错误消息中包含页面路径，便于定位问题。

#### `call_wx` — 调用 wx API

```json
{"action": "call_wx", "method": "getSystemInfo", "args_json": "[]"}
```

#### `mock_wx` — Mock wx API

```json
{
  "action": "mock_wx",
  "method": "requestPayment",
  "result_json": "{\"errMsg\": \"requestPayment:ok\"}"
}
```

常用 Mock 模板：

| 场景 | method | result_json 示例 |
|------|--------|-----------------|
| 支付成功 | `requestPayment` | `{"errMsg": "requestPayment:ok"}` |
| 弹窗确认 | `showModal` | `{"confirm": true, "cancel": false, "errMsg": "showModal:ok"}` |
| 定位授权 | `chooseLocation` | `{"name": "腾讯大厦", "latitude": 22.54, "longitude": 113.93, "errMsg": "chooseLocation:ok"}` |
| 获取用户信息 | `getUserProfile` | `{"userInfo": {"nickName": "测试用户", "avatarUrl": "..."}, "errMsg": "getUserProfile:ok"}` |
| 选择图片 | `chooseImage` | `{"tempFilePaths": ["wxfile://tmp.jpg"], "errMsg": "chooseImage:ok"}` |

#### `evaluate` — 执行 JS 代码

```json
{"action": "evaluate", "expression": "getApp().globalData.userInfo"}
```

支持表达式和声明语句（`const`/`let`/`var`）。表达式模式优先，失败后自动 fallback 到语句模式。

#### `page_stack` — 获取页面栈

```json
{"action": "page_stack"}
```

返回当前所有页面路径的有序列表，最后一个为当前活跃页。

#### `page_data` — 获取当前页面 data

```json
{"action": "page_data"}
{"action": "page_data", "expected_path": "pages/index/index"}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expected_path` | string | null | 期望的页面路径，传入后轮询验证当前页面是否匹配 |

返回当前页面实例的完整 `data` 对象。当传入 `expected_path` 且当前页面不匹配时，返回 `data.path_mismatch: true` 和 `data.warning` 提示信息。

#### `system_info` — 获取系统信息

返回设备信息、操作系统版本、微信版本、屏幕尺寸等。

#### `storage` — 读取本地缓存

```json
{"action": "storage"}           // 列出所有 key
{"action": "storage", "key": "userToken"}  // 读取指定 key 的值
```

---

## 4. wechat_inspector

运行时日志采集。覆盖原 `wechat_get_console_logs`、`wechat_get_cdp_logs`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `console` 或 `cdp` |
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `detail_level` | string | `concise` | `cdp` 时：`concise`（仅 errors+warnings）或 `full`（全量） |
| `max_logs` | int | `50` | `cdp` 时：最大返回条数，超出 `truncated=true` |
| `cdp_port` | int | `9222` | CDP 调试端口 |
| `auto_port` | int | `9420` | 自动化端口，`console` 时使用 |
| `log_type` | string | `all` | `console` 时：`all` / `console` / `exception` |
| `tap_selector` | string | null | 采集期间自动点击的元素（触发懒加载/交互日志） |
| `tap_delay` | int | `500` | 点击延迟（毫秒） |

### action 说明

#### `console` — automator 端口日志

- **采集来源**：9420 自动化端口
- **捕获内容**：`console.log/warn/error` 输出 + JS 运行时异常（堆栈）
- **前提**：先调用 `wechat_automator(action='start')`

```json
{
  "action": "console",
  "duration": 10,
  "log_type": "exception"
}
```

#### `cdp` — CDP 协议底层日志

- **采集来源**：端口 9222（CDP 协议）
- **捕获内容**：WXML 警告、废弃 API 提示、渲染层报错、Runtime 错误
- **前提**：调用 `wechat_ide(action='open', cdp_enabled=True)` 确保端口 9222 已绑定

```json
{
  "action": "cdp",
  "duration": 10,
  "detail_level": "concise",
  "max_logs": 50
}
```

### CDP 返回结构

```json
{
  "success": true,
  "data": {
    "summary": {
      "total": 15,
      "errors": 2,
      "warnings": 5,
      "info": 8,
      "truncated": false
    },
    "logs": [
      {
        "level": "error",
        "message": "Component is not found in path \"components/foo/foo\"",
        "source": "index.wxml",
        "timestamp": "2026-03-19T10:00:01.234Z"
      },
      {
        "level": "warning",
        "message": "wx.getSystemInfoSync 已弃用，请使用 wx.getSystemInfo",
        "source": "app.js",
        "timestamp": "2026-03-19T10:00:01.567Z",
        "column": 12,
        "line": 45
      }
    ]
  },
  "message": "采集 10 秒，发现 2 个错误、5 个警告"
}
```


**detail_level 对比：**

| 模式 | 返回内容 | 适用场景 |
|------|----------|----------|
| `concise` | summary + errors + warnings | 快速诊断（节省 Token） |
| `full` | summary + 所有级别日志 | 深度排查（需要完整上下文） |

---

## 5. wechat_screenshot

捕获当前小程序模拟器界面截图，默认自动滚动拼接长图，保存为 PNG。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | string | `null`（自动生成） | 截图保存路径。留空则自动保存到项目目录下 `screenshots/` 文件夹 |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `overlap` | int | `50` | 分段重叠像素数，防止滚动拼接时内容截断 |
| `full_page` | bool | `true` | 是否截取长图，设为 `false` 只截当前视口 |
| `scroll_top` | int | null | 截图前滚动到的位置（逻辑像素） |
| `page_path` | string | null | 确保截图前在指定页面上 |

### 注意事项

- `output_path` 可选：留空则自动保存到 `{WECHAT_PROJECT_PATH}/screenshots/screenshot_{timestamp}.png`
- 如手动指定路径，父目录会自动创建，无需预先 mkdir
- **前提**：已调用 `wechat_automator(action='start')`
- **不要主动截图**：仅在用户明确要求或排查异常需要视觉确认时才调用
- **限制**：截图可能无法捕获 fixed/absolute 定位的 overlay（弹窗、蒙层），以 `page_data` 为准
- Windows 路径使用正斜杠 `/` 或双反斜杠 `\\` 均可

### 返回示例

```json
{
  "success": true,
  "data": {
    "path": "D:/YourProject/screenshots/screenshot_20260326_143000.png",
    "width": 375,
    "height": 1200,
    "segments": 3,
    "isScrollViewPage": false
  },
  "message": "截图已保存，共拼接 3 段"
}
```

---

## 6. wechat_navigate

跳转到指定页面，等待渲染完成，同步采集 CDP 高清日志。适合检查页面 `onLoad`/`onShow` 阶段的初始化错误。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 页面路径，例如 `pages/index/index`（无需前导 `/`） |
| `wait_ms` | int | `2000` | 跳转后等待时间（毫秒），范围 100~30000 |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `cdp_port` | int | `9222` | CDP 调试端口 |
| `detail_level` | string | `concise` | `concise` 或 `full` |
| `max_logs` | int | `50` | 最大返回 CDP 日志条数 |
| `clear_logs` | `bool` | `true` | 否 | 是否过滤跳转前的 CDP 历史日志（基于时间戳）。设为 `false` 可获取完整累积日志。 |
| `check_data` | `bool` | `true` | 否 | 跳转后检查 page_data，如超过 70% 字段为空且 URL 含 query 参数，追加参数名错误警告。 |
| `project_path` | string | null | 项目路径（仅用于日志提示） |

### 等待时间建议

| 页面复杂度 | 推荐 wait_ms |
|-----------|-------------|
| 简单静态页面 | 1000~2000 |
| 含网络请求的页面 | 3000~5000 |
| 含动画/懒加载的页面 | 5000+ |

### 返回示例

```json
{
  "success": true,
  "data": {
    "current_page": "pages/index/index",
    "navigation_method": "reLaunch",
    "logs_since": "2026-03-25T10:30:00.000Z",
    "filtered_before_navigation": 5,
    "warning": "页面数据大部分为空，可能是 query 参数名错误。",
    "cdp_logs": {
      "summary": {"total": 3, "errors": 0, "warnings": 2, "info": 1, "truncated": false},
      "logs": [...]
    }
  },
  "message": "已跳转到 pages/index/index，采集到 3 条日志"
}
```

---

## 7. wechat_file

项目文件读取。覆盖原 `wechat_project_info`、`wechat_list_pages`、`wechat_read_page`、`wechat_read_file`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `project_info` / `list_pages` / `read_page` / `read_file` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `page_path` | string | null | 页面路径，`read_page` 时**必填**，例如 `pages/index/index` |
| `file_path` | string | null | 相对文件路径，`read_file` 时**必填**，例如 `app.json` |

### action 说明

#### `project_info` — 项目完整信息

返回：
- `project.config.json` 解析结果（AppID、名称、编译条件等）
- `app.json` 解析结果（页面列表、tabBar、全局配置）
- 项目根目录结构（一层）

#### `list_pages` — 页面列表

返回 `app.json` 中注册的所有页面路径，并检查每个页面的 `.wxml`/`.js`/`.wxss`/`.json` 文件是否存在。

#### `read_page` — 读取页面完整源码

```json
{"action": "read_page", "page_path": "pages/index/index"}
```

返回：
- `index.wxml` — 模板结构
- `index.wxss` — 样式
- `index.js` — 逻辑（含 Page/Component 定义）
- `index.json` — 页面配置

#### `read_file` — 读取任意文件

```json
{"action": "read_file", "file_path": "components/header/header.js"}
```

最多返回 800 行，超出时附注截断说明。

---

## 8. 错误码速查表

| error_code | 含义 | 常见原因 | 处理方式 |
|------------|------|----------|----------|
| `PARAM_MISSING` | 必填参数未提供 | 漏传 `selector`、`version` 等 | 查看 `hint` 字段，补充参数 |
| `CLI_NOT_FOUND` | 微信开发者工具 CLI 不存在 | `WECHAT_DEVTOOLS_CLI` 路径错误 | 确认安装路径并更新环境变量 |
| `PROJECT_PATH_MISSING` | 项目路径未配置 | `WECHAT_PROJECT_PATH` 未设置 | 配置环境变量或传入 `project_path` |
| `NODE_NOT_FOUND` | Node.js 未安装或不在 PATH | Node 未安装/`NODE_PATH` 错误 | 安装 Node.js ≥ 8.0 |
| `CLI_TIMEOUT` | CLI 命令执行超时 | IDE 未运行/端口未开启 | 调用 `wechat_ide(action='open')` 后重试 |
| `CDP_CONNECTION_ERROR` | CDP 端口 9222 连接失败 | 未以 `cdp_enabled=True` 启动 | 调用 `wechat_ide(action='open', cdp_enabled=True)` |
| `AUTOMATION_PORT_ERROR` | 自动化端口 9420 连接失败 | 未调用 `start` action | 先调用 `wechat_automator(action='start')` |
| `FILE_NOT_FOUND` | 文件或页面路径不存在 | `page_path`/`file_path` 拼写错误 | 先调用 `list_pages` 确认路径 |

---

*返回 [SKILL.md](../SKILL.md)*
