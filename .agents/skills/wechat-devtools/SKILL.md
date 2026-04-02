---
name: wechat-devtools
description: 微信开发者工具 MCP —— 小程序构建、预览、调试与自动化测试
---

# Wechat DevTools MCP Skill (v0.5.1)

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
| `open` | 打开 IDE/项目（cdp_enabled 时自动做启动健康检查） | `cdp_enabled=true`（开启 CDP 9222 端口，自动采集 5s CDP 日志检测启动错误） |
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

- `output_path`（可选）：截图保存路径。留空则自动保存到项目目录下 `screenshots/` 文件夹
- **前提**：先调用 `wechat_automator(action='start')`
- **注意**：不要主动截图，仅在用户明确要求或排查异常需要视觉确认时才调用

### `wechat_navigate` — 跳转并采集日志

- `page_path`（**必填**）：如 `pages/index/index`
- `wait_ms`：等待毫秒，建议 3000
- `clear_logs`：是否过滤历史 CDP 日志，默认 `true`
- `check_data`：跳转后是否检查 page_data 空值，默认 `true`
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
| `db_collection_add` | 创建数据库集合 | `collection_name` |
| `db_collection_count` | 集合文档计数 | `collection_name` |

> db 系列 action 通过 automator evaluate 执行，需先调用 `wechat_automator(action='start')`。不需要 `env` 参数。

---

## SOP 标准操作流程

### SOP A：初始化（新环境必做）

```
wechat_ide(action='status')                         # 诊断环境
wechat_ide(action='is_login')                       # 检查登录
  ↳ 未登录: wechat_ide(action='login', qr_format='terminal')
wechat_ide(action='open', cdp_enabled=True)         # 开启 IDE + CDP 9222 + 自动健康检查
  ↳ 返回 success=false + startup_errors → 小程序启动阶段有致命错误，必须先修复再继续
  ↳ 返回 success=true → 启动正常，继续后续步骤
wechat_automator(action='start')                    # 开启自动化 9420，等待 3s
wechat_file(action='project_info')                  # [可选] 确认项目结构
wechat_build(action='cache_clean', clean_type='all')     # 清除全部缓存
wechat_build(action='compile')                            # 编译建立干净 CDP 基线
  ↳ ⚠ 检查输出中 AppID 是否为 undefined
  ↳ 如果 undefined → project_path 可能指向了子目录而非项目根目录
  ↳ 云开发项目根目录包含 project.config.json、miniprogram/ 和 cloudfunctions/
  ↳ 正确: project_path="D:/MyProject"  错误: project_path="D:/MyProject/miniprogram"
```

> **project_path 规则**：必须指向包含 `project.config.json` 的根目录。云开发项目的 `miniprogram/` 是子目录，不能作为 project_path。

### SOP B：UI 调试（数据/布局问题）

```
wechat_file(action='list_pages')                           # ⓪ 首次导航前，获取有效页面路径列表
  ↳ tabBar 页面路径通常是 pages/xxx/index（非 pages/xxx/xxx）
wechat_navigate(page_path='pages/xxx/index', wait_ms=3000) # ① 跳转 + CDP 日志
wechat_automator(action='page_data')                       # ② 查看 data 状态
  ↳ ⚠ 必须校验 data.path === 预期的 page_path
  ↳ 如不匹配 → 页面跳转失败或被重定向（见 page_data 注意事项）
  ↳ 数据异常: set_data(data_json='{"key":"val"}')  热更新验证
  ↳ 确认元素: element_info(selector='.target')
  ↳ 仅在用户要求或需要视觉确认时: wechat_screenshot()  # 默认保存到项目 screenshots/
```

### SOP C：异常排查（报错/白屏/JS 异常）

```
wechat_automator(action='page_data')                       # ① 首选：直接检查页面数据
  ↳ 关键字段为 null/空 → 数据未加载或参数错误
  ↳ 数据正常 → 跳到步骤 ④ 确认非数据问题
wechat_automator(action='evaluate', expression='wx.cloud.callFunction({name:"xxx",data:{...}})')
                                                            # ② 直接调 API 获取完整返回值
  ↳ 遇到 [object Object] 时必用此步骤，可拿到完整 JSON
wechat_inspector(action='cdp', duration=5, detail_level='concise')
                                                            # ③ CDP 辅助参考
  ⚠ CDP 错误计数可能包含历史缓存，以 page_data 为准
wechat_build(action='compile')                              # ④ 捕获静态编译错误
```

### SOP D：全页面巡检（回归/发布前验收）

```
wechat_build(action='cache_clean', clean_type='all')    # 建立干净 CDP 基线
wechat_build(action='compile')
  ↳ ⚠ 检查 AppID 是否为 undefined
wechat_file(action='list_pages')                        # 获取页面列表，确认有效路径
# 对每个 page 顺序执行（禁止并行）：
wechat_navigate(page_path=page, wait_ms=3000)           # 跳转 + CDP 日志
wechat_automator(action='page_data')                    # 核心验证：关键字段非 null/空
  ↳ ⚠ 必须校验 data.path === 预期的 page_path
  ↳ 如不匹配 → 页面跳转失败或被重定向，标记异常
  ↳ 字段正常且 path 匹配 → ✅ 页面通过
  ↳ 字段为空 → ⚠ 标记异常，用 evaluate 进一步诊断
  ↳ 仅在 page_data 异常时补充截图
# 汇总：按 page_data 结果排序输出报告
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

### SOP G：子页面测试（需 query 参数的页面）

```
wechat_file(action='read_page', page_path='pages/xxx/xxx')  # ① 查看 onLoad 方法
  ↳ 从 options 参数中确认 query 参数名（如 id / matchId）
wechat_navigate(page_path='pages/xxx/xxx?正确参数名=值', wait_ms=3000)  # ② 跳转
wechat_automator(action='page_data')                          # ③ 验证数据
  ↳ 关键字段非空 → ✅
  ↳ 大部分为 null → 参数名可能有误，回到 ①
```

### SOP H：云函数部署验证

```
wechat_cloud(action='func_deploy', env='xxx', names=['func_name'])  # ① 部署
# 等待 3 秒（部署自动包含延迟验证）
wechat_automator(action='evaluate',                                  # ② 真实调用验证
  expression='wx.cloud.callFunction({name:"func_name",data:{}})')
  ↳ 返回 code:0 → ✅ 部署生效
  ↳ FUNCTION_NOT_FOUND → 等待更久或检查函数名
```

### SOP I：跨页面数据一致性校验

适用场景：验证同一数据在不同页面的展示是否一致（如积分、用户状态、等级等）

```
wechat_file(action='list_pages')                         # ① 获取页面列表
# 定义需要校验的公共字段（如 points, phone_bound, level）
# ② 逐页面采集数据（顺序执行，禁止并行）：
wechat_navigate(page_path=page, wait_ms=3000)
wechat_automator(action='page_data')
  ↳ 校验 data.path === 预期页面（跳转失败则标记并跳过）
  ↳ 提取公共字段值，记录到比对表
# ③ 比对各页面的同名字段值
  ↳ 值一致 → ✅ 字段通过
  ↳ 值不一致 → ⚠ 标记异常，用 evaluate 直接调 API 对比返回值
  ↳ 子页面数据异常时，检查是否使用了独立的数据获取链路
```

### SOP J：小程序 + 管理后台并行数据比对

适用场景：验证小程序前端数据与管理后台数据的一致性

```
# 架构：
#   管理后台 → Playwright MCP（浏览器端口）
#   小程序   → WeChat DevTools MCP（automator 9420 端口）
#   两者使用不同端口，可以并行运行

# ① 分别从两端提取数据（可并行）
#   Agent A: Playwright 操作管理后台，提取数据
#   Agent B: WeChat MCP 操作小程序，提取 page_data
# ② 在主进程中做数据比对（串行）
```

> **端口独占规则**：automator 9420 端口是独占的，同一时刻只能有一个 Agent 操作 WeChat MCP。Playwright 和 WeChat MCP 可同时使用（不同端口）。

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

> **重要**：CDP 错误计数可能包含跨页面累积的历史日志。v0.4.0 的 `clear_logs=true`（默认）会基于时间戳过滤历史日志，但仍建议以 `page_data` 作为最终验证标准。

### CDP 日志噪音过滤

以下日志来源属于开发工具内部噪音，**不代表应用错误**，应在判断时排除：

| source 前缀 | 说明 | 处理 |
|-------------|------|------|
| `devtools://devtools/` | 开发者工具自身的断言/警告 | 忽略 |
| `ide:///extensions/` | IDE 扩展注入的提醒 | 区分对待 |

以下 message 模式属于框架级提醒，非应用错误：

| message 模式 | 说明 |
|-------------|------|
| `console.assert` | devtools 内部断言 |
| `SharedArrayBufferIssue` | 浏览器引擎警告 |
| `getSystemInfo API 提示` | 废弃 API 迁移提醒 |
| `wx.saveFile 即将废弃` / `wx.removeSavedFile 即将废弃` | 框架 API 废弃预警 |
| `[Component] property "xxx" received type-uncompatible value` | 组件属性类型不匹配警告 |

> **判断原则**：CDP 的 errors/warnings 计数可能被上述噪音抬高，导致误判。始终以 `page_data` 返回的实际数据作为最终验证标准。

---

## page_data 使用注意事项

1. **必须校验 path 字段**：返回的 `data.path` 表示当前实际页面，如果与导航目标不一致，说明页面跳转失败或被重定向。

2. **常见不一致原因**：
   - 用户未登录，页面拦截跳转到登录/欢迎页
   - 云函数调用失败（AppID undefined），页面 fallback 到首页
   - page_path 拼写错误，navigate 静默失败（返回 success: true）
   - 页面 onLoad 中有条件跳转逻辑

3. **推荐模式**：
   ```
   wechat_navigate(page_path='pages/xxx/index', wait_ms=3000)
   wechat_automator(action='page_data')
     ↳ data.path !== 'pages/xxx/index' → 页面未正确加载
     ↳ 用 page_stack 查看完整页面栈，定位重定向原因
   ```

---

## 返回值格式

```json
{"success": true,  "data": {...}, "message": "操作描述"}
{"success": false, "error_code": "CLI_TIMEOUT", "message": "...", "hint": "修复提示"}
{"success": false, "error_code": "UNKNOWN_ERROR", "message": "小程序启动阶段检测到 N 个错误...", "hint": "...", "startup_errors": [...], "cdp_summary": {...}}
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
| `Using AppID: undefined` | project_path 指向子目录而非项目根目录 | 改为包含 `project.config.json` 的目录 |
| `appid missing` 云函数失败 | AppID 未配置或未登录 | 检查 project_path + 登录状态 |
| `Connection closed` 截图/操作失败 | automator WS 连接断开 | 执行恢复流程：`open` → `start` → `compile` |
| `Failed connecting to ws://localhost:9420` | automator 未启动或已断开 | 同上 |
| navigate 返回 success 但页面未跳转 | page_path 不存在或拼写错误 | `list_pages` 确认路径；用 `page_stack` 验证 |
| page_data.path 与 navigate 目标不一致 | 页面被重定向（未登录/参数错/云函数失败） | 检查 AppID、登录状态、页面 onLoad 逻辑 |
| CDP errors 计数含 console.assert | devtools 内部噪音 | 过滤 `devtools://` 来源，以 page_data 为准 |
| 子页面数据与主页面不一致 | 子页面使用独立数据获取链路 | 用 `evaluate` 直接调用 API 对比返回值 |
| 长图截图底部导航栏重复出现 | 固定区域检测失败（已在 v0.5.0 修复） | 升级到最新版本；如仍复现请反馈 |
| `open` 返回 startup_errors | 小程序启动阶段有致命错误（页面无法显示） | 根据 `startup_errors` 中的错误详情修复代码，修复后重新 `open` |

### 连接断开恢复流程

当截图或自动化操作报 `Connection closed` 或 `ws://localhost:9420` 连接失败时，执行以下标准恢复流程：

```
wechat_ide(action='open', project_path='...', cdp_enabled=true)   # ① 重新打开项目
wechat_automator(action='start', project_path='...')               # ② 重启 automator
wechat_build(action='compile', project_path='...')                 # ③ 重新编译
# ④ 重试失败的操作
```

---

## 绝对红线

- ❌ `open` 返回 `startup_errors` 后仍继续执行后续测试操作（必须先修复错误）
- ❌ 未确认 `is_login: true` 时调用 `preview` / `upload`
- ❌ 对生产项目调用 `cache_clean(clean_type='all')`
- ❌ 在 `evaluate` 中执行 `eval()` 或不安全代码
- ❌ 脑补运行状态——必须以 MCP 接口返回的实际数据为准
- ❌ 同一失败操作重试超过 3 次（应转为诊断根因）
- ❌ 自动化测试中使用 `sleep` 硬等待（用 `wait_ms` 或轮询 `page_data`）
- ❌ 在 SOP 流程中主动调用截图——仅在用户明确要求或异常排查需要视觉确认时才截图
- ❌ 使用 `miniprogram/` 子目录作为云开发项目的 project_path
- ❌ navigate 后不校验 `page_data.path` 是否匹配预期页面
- ❌ 将 CDP 日志中 `devtools://` 来源的 `console.assert` 视为应用错误
- ❌ 在多个并行 Agent 中同时使用 `wechat_automator`（9420 端口独占）
- ✅ `wechat_screenshot` 的 `output_path` 可选，留空自动保存到项目 `screenshots/` 目录
- ✅ 使用任何自动化/截图功能前必须先调用 `automator(action='start')`
- ✅ 执行 `tap`/`input` 前先用 `element_info` 确认元素存在
- ✅ `upload` 前确认版本号已递增，`build_npm` 已执行
- ✅ 关注 CDP 日志中的 `[Violation]` 标记（渲染阻塞/性能问题）
- ✅ `compile` 后检查 AppID 是否为 undefined
- ✅ 截图/操作失败后执行 `open` → `start` → `compile` 恢复连接
- ✅ navigate 后必须通过 `page_data` 或 `page_stack` 校验当前页面路径
- ✅ 在跨页面测试中比对同名字段的一致性
