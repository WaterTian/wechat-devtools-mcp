# MCP 工具箱完整文档 (v0.4.1)

v0.3.0 采用「**瘦 MCP + 胖 Skill**」架构，将 44 个工具聚合为 **8 个聚合工具**。每个工具通过 `action` 参数切换功能子集，覆盖小程序全生命周期。

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
8. [wechat_cloud — 云函数管理](#wechat_cloud)
9. [Mock 场景示例](#mock-场景示例)

---

## wechat_ide

IDE 生命周期管理。合并原 `wechat_open`、`wechat_login`、`wechat_is_login`、`wechat_close_project`、`wechat_quit_ide`、`wechat_get_status`。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `open` | 打开 IDE 或指定项目（每次自动编译刷新） | — |
| `login` | 登录，生成二维码供扫码 | — |
| `is_login` | 检查是否已登录 | — |
| `close` | 关闭指定项目窗口 | — |
| `quit` | 退出整个 IDE | — |
| `status` | 环境诊断（CLI/项目路径/Node.js/项目信息） | — |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言：`en` 或 `zh` |
| `cdp_enabled` | bool | `true` | 是否开启 CDP 调试端口（9222），`open` 时使用 |
| `qr_format` | string | `terminal` | 二维码格式，`login` 时使用 |
| `qr_output` | string | null | 二维码输出路径，`login` 时使用 |

---

## wechat_build

构建与发布。合并原 `wechat_compile_check`、`wechat_preview`、`wechat_upload`、`wechat_build_npm`、`wechat_cache_clean`。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `compile` | **[最常用]** 触发编译，捕获所有 Error 和 Warning | — |
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
| `qr_format` | string | `base64` | 二维码格式 |
| `qr_output` | string | null | 二维码输出文件路径 |
| `info_output` | string | null | 编译/上传信息输出 JSON 路径 |
| `compile_condition` | string | null | 自定义编译条件（JSON 字符串） |
| `compile_type` | string | null | 编译类型：`miniprogram` 或 `plugin` |
| `clean_type` | string | `compile` | 缓存类型：`storage`、`file`、`compile`、`auth`、`network`、`session`、`all` |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

---

## wechat_automator

自动化交互与运行时查询。合并所有原自动化工具（13 个 action）。

> **前提**：需先调用 `wechat_automator(action='start')` 开启 9420 自动化端口，**只需一次**。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `start` | 开启自动化端口，监听连接 | — |
| `tap` | 模拟点击指定元素 | **`selector`** |
| `input` | 向 input/textarea 输入文本 | **`selector`**, **`value`** |
| `element_info` | 获取元素详情（文本/尺寸/位置/WXML） | **`selector`** |
| `set_data` | 热更新页面 data，无需重新编译 | **`data_json`** |
| `call_method` | 调用当前页面的指定方法 | **`method`** |
| `call_wx` | 直接调用 wx 对象上的方法 | **`method`** |
| `mock_wx` | Mock wx API 的返回值 | **`method`**, **`result_json`** |
| `evaluate` | 在逻辑层执行 JS 表达式 | **`expression`** |
| `page_stack` | 获取当前页面栈信息 | — |
| `page_data` | 读取当前活跃页面的 data 状态 | — |
| `system_info` | 获取运行时系统信息 | — |
| `storage` | 获取本地缓存数据（key 为空则列出所有） | — |

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `project_path` | string | 环境变量 | 小程序项目路径，`start` 时使用 |
| `selector` | string | null | CSS 选择器，例如 `.submit-btn`、`#login` |
| `value` | string | null | 输入值 |
| `style_prop` | string | null | 要查询的 CSS 属性名，`element_info` 时可选 |
| `data_json` | string | null | JSON 数据字符串，例如 `{"key": "val"}` |
| `method` | string | null | 方法名 |
| `args_json` | string | null | 方法参数（JSON 数组字符串） |
| `expression` | string | null | JS 表达式，例如 `getApp().globalData` |
| `result_json` | string | null | Mock 返回值（JSON 字符串） |
| `key` | string | null | Storage key，为空则列出所有 key |
| `auto_account` | string | null | 指定 openid，`start` 时可选 |

---

## wechat_inspector

运行时日志采集。合并原 `wechat_get_console_logs`、`wechat_get_cdp_logs`。

**必填参数**：`action`

| action | 功能 | 采集来源 |
|--------|------|---------|
| `console` | 采集 console 日志和 JS 运行时异常 | automator 端口 |
| `cdp` | 采集底层高清日志（WXML 警告/废弃 API/渲染层报错） | CDP 9222 端口 |

> **cdp 前提**：调用 `wechat_ide(action='open', cdp_enabled=True)` 确保端口 9222 可用。

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | **必填** | `console` 或 `cdp` |
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `detail_level` | string | `concise` | `cdp` 时使用：`concise`（仅 errors+warnings）或 `full`（全量） |
| `max_logs` | int | `50` | `cdp` 时使用：最大返回条数，超出时 `truncated=true` |
| `cdp_port` | int | `9222` | CDP 调试端口 |
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
      {"level": "error", "message": "Cannot read property ...", "source": "index.js", "timestamp": "...", "line": 45, "column": 12}
    ]

  },
  "message": "采集 10 秒，发现 2 个错误、1 个警告。"
}
```

---

## wechat_screenshot

捕获当前小程序模拟器的界面截图，默认支持滚动拼接长图，保存为 PNG 文件。

> **前提**：需先调用 `wechat_automator(action='start')` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | string | **必填** | 截图保存路径（绝对路径），例如 `D:/screenshots/page.png` |
| `auto_port` | int | `9420` | 自动化端口 |
| `overlap` | int | `50` | 分段重叠像素数，防止内容截断 |

---

## wechat_navigate

跳转到指定页面，等待指定时间，同步采集 CDP 高清日志。适合检查页面初始化（`onLoad`、`onShow`）阶段的错误。

> **前提**：需先调用 `wechat_automator(action='start')` 并以 `cdp_enabled=True` 打开项目。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 要跳转的页面路径，例如 `pages/index/index` |
| `wait_ms` | int | `2000` | 跳转后等待时间（毫秒），范围 100~30000 |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `cdp_port` | int | `9222` | CDP 调试端口 |
| `detail_level` | string | `concise` | `concise`（仅 errors+warnings）或 `full` |
| `clear_logs` | bool | `true` | 是否过滤跳转前的 CDP 历史日志（基于时间戳）。设为 `false` 可获取完整累积日志。 |
| `check_data` | bool | `true` | 跳转后检查 page_data，如超过 70% 字段为空且 URL 含 query 参数，追加参数名错误警告。 |
| `max_logs` | int | `50` | 最大返回 CDP 日志条数 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

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

---

## wechat_cloud

云函数管理。合并原 5 个云函数工具。

**必填参数**：`action`

| action | 功能 | 条件必填参数 |
|--------|------|------------|
| `env_list` | 列出所有关联的云开发环境 | — |
| `func_list` | 列出指定环境的线上云函数 | **`env`** |
| `func_info` | 查看指定云函数的详细信息 | **`env`**, **`names`** |
| `func_deploy` | 上传云函数到云环境 | **`env`** |
| `func_download` | 从云环境下载云函数到本地 | **`env`**, **`name`**, **`download_path`** |
| `db_collection_add` | 创建数据库集合 | **`collection_name`** |
| `db_collection_count` | 查询集合文档数量 | **`collection_name`** |

> **注意**：`db_collection_add` 和 `db_collection_count` 通过 automator evaluate 执行，不需要 `env` 参数，但需先调用 `wechat_automator(action='start')`。

**可选参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `env` | string | null | 云环境 ID，多数 action 必填 |
| `names` | list[string] | null | 云函数名称列表，`func_info`/`func_deploy` 使用 |
| `paths` | list[string] | null | 云函数目录绝对路径，`func_deploy` 使用 |
| `name` | string | null | 云函数名称，`func_download` 必填 |
| `download_path` | string | null | 下载存放路径，`func_download` 必填 |
| `collection_name` | string | null | 数据库集合名称，`db_collection_add`/`db_collection_count` 时**必填** |
| `auto_port` | int | `9420` | 自动化端口，db 系列 action 使用 |
| `remote_npm_install` | bool | `false` | 是否云端安装依赖 |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

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
