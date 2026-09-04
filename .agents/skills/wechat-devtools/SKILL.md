---
name: wechat-devtools
version: 0.9.17
description: 微信开发者工具 MCP —— 小程序构建、预览、调试与自动化测试
---

# Wechat DevTools MCP Skill (v0.9.17)

## 前置条件

### Step 0：安装与配置

```bash
pip install uv
uv tool install wechat-devtools-mcp --force
```

```json
{
  "mcpServers": {
    "wechat-devtools-mcp": {
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

- 注册名用 `wechat-devtools-mcp`（开发者工具 2.x 把自家 MCP bridge 注册成 `wechat-devtools`，同名会被覆盖）。macOS CLI 路径 `/Applications/wechatwebdevtools.app/Contents/MacOS/cli`。各编辑器配置见 [README](https://github.com/WaterTian/wechat-devtools-mcp#step-4--编辑器配置)。
- **必须开启服务端口**：`设置 → 安全设置 → 服务端口`。未开启则所有 CLI 操作报 `CLI_TIMEOUT`。

### Step 1：运行时环境检查

先调 `wechat_ide(action='status')` 一次确认全部前置条件：

| 检查项 | 字段 | 失败时 |
|--------|------|--------|
| CLI 已安装 | `cli_exists: true` | 配置 `WECHAT_DEVTOOLS_CLI` |
| 服务端口已开启 | `service_port_enabled: true` | `false` 必然 `CLI_TIMEOUT`，去设置里打开；`null` 是读不到，不等于关闭 |
| 项目路径有效 | `project_exists: true` | 配置 `WECHAT_PROJECT_PATH`，须指向含 `project.config.json` 的根目录 |
| Node.js 可用 | `node_available: true` | 安装 Node.js |
| 版本一致 | `mcp_version` == 本文件 `version` | `uv tool upgrade wechat-devtools-mcp` 或同步 skill 副本 |
| 已登录 | `is_login` → `logged_in: true` | `login(qr_format='terminal')` 扫码 |
| 官方内建 MCP | `official_mcp.available` | 见下方分流规则 |

### 环境分流规则（IDE 2.x 内建 MCP）

开发者工具 2.x（2026-08-18 起为官方 Stable）在 `http://127.0.0.1:<ide_port>/mcp` 内建 MCP Server（47 个原子工具）。`official_mcp.available: true` 且官方 MCP 已接入当前 agent 时：

| 操作 | 交给谁 |
|------|--------|
| 开关项目、登录、编译、预览、上传、build npm、点击/输入/滚动、云开发 | 官方工具优先，同一操作不要两边各做一遍 |
| 长图拼接截图 | 本 skill。官方 `simulator_screenshot` 只截视口且压到长边 1280 JPEG |
| CDP 结构化日志（`inspector cdp` / `navigate`） | 本 skill。能回放采集前的历史消息并过滤噪音 |
| SOP C / D / I / J 任务级流程 | 本 skill 编排，基础步骤可调官方工具 |

`available: false`（1.06、IDE 未启动、端口漂移）或官方 MCP 未接入时，本 skill 承接全部能力，不要让用户为基础操作去装官方 MCP。

### 效率原则

- IDE 只在会话开始 `open` 一次；改了代码只需 `compile` → `page_data`（自动重连 automator），不要重新 open。
- 没改代码换页面用 `evaluate(fn_source="function(){ wx.reLaunch({url:'/pages/x/index'}); return 'ok' }")` → `page_data`。
- 连接断开先 `start` → `page_data`，不要直接走完整恢复。

## API 速查表

完整参数与返回字段见 [tool_reference.md](references/tool_reference.md)。

### `wechat_ide`

| action | 功能 | 关键参数 / 返回 |
|--------|------|----------------|
| `open` | 启动 IDE 并打开项目。`cdp_enabled=true`（默认）会 kill 已运行的 IDE、带 CDP 端口重启，等小程序 target 就绪后做启动健康检查 | `cdp_port`（默认 9222，被占用时换，须与 inspector/navigate/compile 一致）；返回 `ide_runtime`、`cdp_ready`、`project_opened`；有 error 时 `success:false` + `startup_errors` |
| `login` / `is_login` | 扫码登录 / 查登录态 | `qr_format`；`logged_in` |
| `close` / `quit` | 关项目窗口 / 退出 IDE | 无 |
| `status` | 环境诊断 | `service_port_enabled`、`ide_port`、`official_mcp`、`mcp_version` |

### `wechat_build`

| action | 功能 | 关键参数 / 返回 |
|--------|------|----------------|
| `compile` | 编译并捕获 Error/Warning，成功后自动重连 automator（仅默认 9420） | `cdp_port`；返回 `errors`、`warnings`、`wxml_errors`、`npm_warning`、`automator_verified`、`fatal_errors` |
| `preview` | 生成预览二维码 | `qr_format`、`qr_output`（相对路径相对项目根）；返回 `qr_stale_warning` 表示 bundle 可能没刷新 |
| `upload` | 上传到微信后台，生产操作 | `version` 必填，`desc` |
| `build_npm` | 构建 npm。新增/更新依赖后必做，否则运行时报 `module ... is not defined` | 无 |
| `cache_clean` | 清缓存 | `clean_type`（默认 `compile`；`all` 慎用） |

`compile_condition` 对 tabBar 页可能被 app 路由守卫覆盖，跳转用 evaluate 更可靠。

### `wechat_automator`

先调 `start` 开启自动化端口，整个会话一次。

| action | 功能 | 必填 / 返回 |
|--------|------|-------------|
| `start` | 开自动化端口，CLI + TCP + WS 三重验证；窗口未加载完时自动重跑 `cli auto`（最多 3 轮） | 返回 `verified`；`false` 时按 `retry_after_ms` 重试 |
| `tap` / `input` | 点击 / 输入 | `selector`（`input` 另需 `value`） |
| `element_info` | 元素 `tagName/text/wxml/size/offset`，`style_prop` 时带 `style` | `selector` |
| `set_data` | 热更新页面 data，无需重编译 | `data_json`；返回 `updated_keys` |
| `call_method` | 调页面方法 | `method`、`args_json?`；返回 `return_value`、`path` |
| `call_wx` / `mock_wx` | 调 wx API / Mock 返回值（当前会话有效） | `method`（mock 另需 `result_json`） |
| `evaluate` | 逻辑层执行 JS | `fn_source`（推荐）或 `expression`；返回 `result`、`mode` |
| `page_stack` | 页面栈 | 返回 `depth`、`pages` |
| `page_data` | 当前页 data | `expected_path?` 会轮询等页面匹配；返回 `path`、`data`、`path_mismatch` |
| `system_info` / `storage` | 系统信息 / 本地缓存 | `storage` 传 `key` 取值，不传列 `keys` |

evaluate 用法：
- `fn_source` 传完整函数源码（`function(){...}` 或箭头函数），入参放 `args_json`（JSON 数组）。多语句、声明、`return` 都由函数体决定，`mode: "function"`。
- `expression` 只传单个表达式。多语句会退回语句模式（全部执行，`mode: "statement"`），没有 `return` 时结果为 `null` 并附 `hint`。
- 例：`fn_source="function(){ const p=getCurrentPages(); return p[p.length-1].route }"`。

### `wechat_inspector`

| action | 功能 | 关键参数 |
|--------|------|---------|
| `cdp` | CDP 采集 WXML 警告、渲染层报错、Runtime 错误。**能回放采集前的历史消息** | `duration=10`、`detail_level`、`max_logs`、`cdp_port` |
| `console` | automator 事件采集 console 与 JS 异常。只收连接后的事件 | `duration`（排查异常 ≥8s）、`log_type`、`tap_selector` |

排查「刚才报的错」用 `cdp`；要与交互严格对齐时间线才用 `console`。

### `wechat_screenshot`

- `full_page`（默认 true）长图拼接，`false` 只截视口，可配 `scroll_top`；`page_path` 不匹配时自动跳转；`output_path` 留空存到项目 `screenshots/`。
- 只在用户要求或需要视觉确认时截图；fixed/absolute 弹窗蒙层可能拍不到，以 `page_data` 为准。

先看 `message` 有无 ⚠。以下情况图看着连续但不完整：

| 返回字段 | 含义 | 应对 |
|---------|------|------|
| `is_scroll_view_page: true` | 页面靠 scroll-view 滚动，只截到视口 | 用 `evaluate` 读数据代替视觉确认 |
| `truncated: true` | 超分段上限，底部没拍到 | `full_page=false` + `scroll_top` 分段截 |
| `content_gaps: N` | 固定头尾吃光重叠，N 处内容丢失 | 调大 `overlap`（如 150）重试 |
| `detection_confident: false` | 固定头尾识别不可靠 | 结果仅供参考 |

`fixed_header` / `fixed_footer` 是识别到的固定区高度（物理像素）。

### `wechat_navigate`

- `page_path` 必填，可带 query；tabBar 页自动走 `switchTab`，其余 `reLaunch`（返回 `navigation_method`）。
- `wait_ms` 默认 2000，含网络请求的页面建议 3000。`clear_logs=true` 过滤跳转前的历史 CDP 日志。
- 返回 `current_page`、`cdp_logs`、`navigation_mismatch`；带 query 且 `check_data=true` 时数据大面积为空会给 `warning`（疑似参数名错）。
- 前提：`start` 已调用且项目以 `cdp_enabled=true` 打开。reLaunch 进入的页面云函数调用可能丢上下文，非 tabBar 页优先 evaluate + `wx.navigateTo`。

### `wechat_file`

| action | 功能 | 必填 / 返回 |
|--------|------|-------------|
| `project_info` | `project_config`、`app_config`、`directory`、`app.js`/`app.wxss` 节选 | 无 |
| `list_pages` | app.json 全部页面，含文件完整性 | 返回 `pages[{path, complete, missing}]`、`total` |
| `read_page` | 页面四件套源码 | `page_path`；返回 `files{文件名: 内容}`、`resolved_base` |
| `read_file` | 任意单文件，最多 800 行 | `file_path`；返回 `content`、`resolved_path`、`truncated` |

路径口径统一：先按 `miniprogramRoot` 解析再回退项目根，`list_pages` 的输出可直接喂给 `read_page`。

云函数与云数据库请用 [CloudBase MCP](https://github.com/TencentCloudBase/CloudBase-AI-ToolKit)。

## SOP 标准操作流程

### SOP A：初始化

```
wechat_ide(action='status')                    # 环境诊断
wechat_ide(action='is_login')                  # 未登录 → login(qr_format='terminal')
wechat_ide(action='open', cdp_enabled=True)    # 9222 被占用时加 cdp_port=9223
  ↳ success=false + startup_errors → 先修复再继续
wechat_automator(action='start')               # verified=false → 按 retry_after_ms 重试，期间可先 compile
wechat_build(action='compile')                 # 建立干净基线，自动重连 automator
wechat_automator(action='page_data')           # 验证连接；AppID undefined → project_path 指到子目录了
```

project_path 必须是含 `project.config.json` 的根目录，云开发项目的 `miniprogram/` 是子目录。

### SOP A-2：改代码后

```
wechat_build(action='compile') → wechat_automator(action='page_data')
```

不需要重新 open，也不需要 cache_clean。

### 页面跳转

| 场景 | 方式 |
|------|------|
| 普通页 | `evaluate(fn_source="function(){ wx.navigateTo({url:'/pages/x/x?id=1'}); return 'ok' }")` |
| tabBar 页 | `wechat_navigate(page_path='pages/x/index')` |
| 强制重置 | 同上用 `wx.reLaunch` |
| 跳转后 | `page_data(expected_path='pages/x/x')`，校验 `path` |

### SOP B：UI 调试

```
wechat_file(action='list_pages')                            # 拿有效路径
wechat_navigate(page_path='pages/x/index', wait_ms=3000)    # 跳转 + CDP 日志
wechat_automator(action='page_data')                        # path 必须等于目标页
  ↳ 数据异常 → set_data 热更新验证；元素问题 → element_info；需要看图才 screenshot
```

### SOP C：异常排查（报错 / 白屏 / JS 异常）

```
wechat_automator(action='page_data')                        # ① 关键字段 null → 数据没加载
wechat_automator(action='evaluate', fn_source='function(){ return wx.cloud.callFunction({name:"x",data:{}}) }')
                                                            # ② 直接调 API 拿完整返回，[object Object] 时必用
wechat_inspector(action='cdp', duration=5)                  # ③ 能回放刚才的错误
wechat_build(action='compile')                              # ④ 看 errors / wxml_errors
```

### SOP D：全页面巡检

```
wechat_build(action='compile')
wechat_file(action='list_pages')
# 逐页顺序执行（禁止并行）：
wechat_navigate(page_path=page, wait_ms=3000)
wechat_automator(action='page_data', expected_path=page)    # path 不匹配 → 标记重定向；字段空 → evaluate 诊断
# 汇总：按 page_data 结果输出报告；只在异常页补截图
```

### SOP E：Mock 集成测试（支付 / 权限 / 网络 / 适配）

```
mock_wx(method='requestPayment', result_json='{"errMsg":"requestPayment:ok"}')
mock_wx(method='getLocation',    result_json='{"latitude":23.1,"longitude":113.3}')
mock_wx(method='request',        result_json='{"errMsg":"request:fail timeout"}')   # 模拟超时
mock_wx(method='getSystemInfo',  result_json='{"theme":"dark","windowWidth":1024}') # 暗色 / 宽屏适配
tap(selector='.pay-btn') → page_data                                                 # 触发并验证
```

Mock 仅当前会话有效。拦截请求可用 `fn_source="function(){ var o=wx.request; wx.request=function(p){ console.log(p.url); return o.apply(wx,arguments) }; return 'ok' }"`。

### SOP G：带 query 参数的子页面

```
wechat_file(action='read_page', page_path='pages/x/x')      # 看 onLoad(options) 的参数名
wechat_navigate(page_path='pages/x/x?id=123', wait_ms=3000)
wechat_automator(action='page_data')                        # 大部分为 null → 参数名错，回到第一步
```

### SOP I：跨页面数据一致性

```
wechat_file(action='list_pages')
# 逐页：navigate → page_data(expected_path=page)，提取公共字段（如 points / level）记入比对表
# 比对同名字段：不一致 → evaluate 直接调 API 对比，检查子页面是否走了独立数据链路
```

### SOP J：小程序 + 管理后台并行比对

管理后台走 Playwright MCP，小程序走本 MCP，两者端口不同可并行提取，比对在主进程串行做。automator 9420 独占，同一时刻只能有一个 agent 操作本 MCP。

## CDP 日志策略

| 场景 | 参数 |
|------|------|
| 快速诊断 | `duration=5, detail_level='concise', max_logs=20` |
| 深度排查 | `duration=10, detail_level='full', max_logs=100` |
| 页面巡检 | `duration=3, detail_level='concise', max_logs=30` |

- `concise` 只回 errors + warnings；`summary.errors > 0` 再用 `full` 拿 `source` 定位，配合 `read_file`。
- `cdp` 会回放采集前的缓冲区（12 秒前的错误也能拿到），`console` 只收连接后的事件。
- 已自动过滤：`[system]`、`WAService.js`、`WAWebview.js`、IDE 外壳页；`open` 的启动检查还过滤 `devtools://` 与 `ide:///extensions/`。
- 需要自己排除：`devtools://` 来源的 `console.assert`、`SharedArrayBufferIssue`、`wx.saveFile 即将废弃` 类框架预警。
- `ide:///extensions/inject/…` 来源的 warning **不是噪音**，是框架报的真实问题（无效 app.json 字段、API 废弃、WXSS 选择器不合法）。
- 计数可能被噪音抬高，最终以 `page_data` 为准。

page_data 必须校验 `data.path` 等于导航目标；不一致的常见原因：未登录被拦到登录页、云函数失败 fallback 首页、page_path 拼错、onLoad 条件跳转。传 `expected_path` 可轮询等待匹配，`path_mismatch: true` 时用 `page_stack` 看完整栈。

## 返回值与恢复

成功 `{"success": true, "data": {...}, "message": "..."}`，失败 `{"success": false, "error_code": "...", "message": "...", "hint": "..."}`。
`error_code` 只有 6 种：`PARAM_MISSING`、`CLI_NOT_FOUND`、`PROJECT_PATH_MISSING`、`NODE_NOT_FOUND`、`CLI_TIMEOUT`、`UNKNOWN_ERROR`。连接失败、跳转失败等都归 `UNKNOWN_ERROR`，看 `message` 与 `hint`。

连接断开恢复分两级：
1. 快速：`start` → `page_data`。
2. 完整：`open(cdp_enabled=True)` → `start` → `compile` → `page_data`。

## 故障速查

| 症状 | 原因 | 解决 |
|------|------|------|
| `CLI_TIMEOUT` | 服务端口未开 / IDE 未运行 | `status` 看 `service_port_enabled`；开端口；`open` |
| `open` 返回 `startup_errors` | 小程序启动阶段有致命错误 | 先修代码再 `open` |
| `start` 连续 `verified=false` | 冷启动 automator WS 握手未就绪 | 按 `retry_after_ms` 重试；期间先 compile / build_npm |
| `CLI auto 连续 3 次返回成功但端口未监听` | 项目窗口没加载完或已关闭（`cli auto` 会假成功；纯 CLI open 后约需 15s） | 稍等再 `start`；仍失败 `open(cdp_enabled=True)` 重启后再 `start` |
| 任意 automator 动作报 `Failed connecting to ws://localhost:9420` | 项目窗口已关闭或自动化未开（IDE 2.x 偶发窗口自关） | 按返回的 `hint`：先 `start`，仍失败 `open(cdp_enabled=True)` 重开 |
| `Failed connecting to ws://localhost:9420` / `Connection closed` | automator 未启动、断开，或项目窗口已关 | 快速恢复失败再完整恢复 |
| CDP 采集失败 / 采到的全是别的东西 | 未以 `cdp_enabled` 打开，或 9222 被 Chrome 占用（`curl 127.0.0.1:9222/json/version` 可确认） | `open(cdp_port=9223)`，inspector / navigate / compile 用同一端口 |
| `Using AppID: undefined` / `appid missing` | project_path 指向子目录 / 未登录 | 改为含 `project.config.json` 的根目录；`is_login` |
| navigate 后 `page_data.path` 与目标不一致 | page_path 拼错、被重定向（未登录 / 参数错 / 云函数失败）、switchTab 未完成 | `list_pages` 核对；查登录态与 onLoad 逻辑；增大 `wait_ms` |
| evaluate 返回 `null` 且 `mode: "statement"` | `expression` 走了语句模式没 `return` | 改用 `fn_source` 并显式 `return` |
| 元素未找到 / `Element is obfuscated` | 不在当前页、selector 错、被遮挡 | `page_stack` 确认页面；`element_info` 验证；换父节点 |
| scroll-view 页长图只有一屏 | automator 无法捕获 scroll-view 内部滚动 | 返回 `is_scroll_view_page: true`，改用 evaluate 读数据 |
| 长图看着连续但少一截 | 固定头尾吃光重叠 | 看 `content_gaps`，增大 `overlap` |
| 截图看不到弹窗 / 拍到错误页面 | overlay 不在同一渲染层 / 截图前页面被重置 | 以 `page_data` 为准；传 `page_path` |
| compile 成功但 IDE 显示红色 WXML 错误 | WXML 错误走 IDE 内部通道 | 看 `wxml_errors`；检查中文引号、未闭合标签 |
| 运行时报 `@babel/runtime/helpers/xxx is not defined` | npm 依赖更新后未 build_npm | `build_npm` → `compile`，`console(duration≥8, log_type='exception')` 验证 |
| 工具行为异常 / 参数对不上（IDE 2.x） | 注册名撞车：官方 bridge 也叫 `wechat-devtools` | 注册名改 `wechat-devtools-mcp`；`status` 的 `mcp_version` 可确认调到谁 |
| Windows 上 `open` 后项目没打开 / CDP 连不上（IDE 2.x） | 旧版 Windows 分支没有 1.x/2.x 判定 | 升级到最新版；仍失败附 `ide_runtime` 反馈 |
| `ide:///extensions/inject/…` 的 warning | 框架报的真实应用问题 | 当真实告警处理，不要过滤 |

## 绝对红线

- ❌ `open` 返回 `startup_errors` 后继续测试
- ❌ 未确认 `logged_in: true` 就 `preview` / `upload`
- ❌ 对生产项目 `cache_clean(clean_type='all')`
- ❌ 脑补运行状态；同一失败操作重试超过 3 次（应转为诊断根因）
- ❌ 硬 sleep 等待，用 `wait_ms` 或 `page_data(expected_path)` 轮询
- ❌ SOP 里主动截图，只在用户要求或需要视觉确认时截
- ❌ 没改代码就 compile
- ❌ navigate 后不校验 `page_data.path`
- ❌ 多个 agent 并行使用 `wechat_automator`（9420 独占）
- ❌ 用 `miniprogram/` 子目录作 project_path；WXML 属性值里用中文引号（工具无法检测）
- ✅ 自动化 / 截图前先 `start`；`tap` / `input` 前先 `element_info` 确认元素
- ✅ `upload` 前确认版本号递增、`build_npm` 已执行
- ✅ compile 后用 `page_data` 确认 automator 连接
