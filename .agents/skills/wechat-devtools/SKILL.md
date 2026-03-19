---
name: wechat-devtools
description: |
  微信小程序开发调试知识库。提供 8 个聚合 API 的 SOP 流程、参数速查和最佳实践。
  当需要使用微信开发者工具 MCP（wechat_ide / wechat_build / wechat_automator 等）时使用本 Skill。
---

# Wechat DevTools MCP Skill

## 核心前置条件（每次使用前必须确认）

### Step 0：安装并配置 MCP Server

使用本 Skill 前，必须先在编辑器中配置 `wechat-devtools-mcp` MCP Server。

**安装（需要 [uv](https://github.com/astral-sh/uv)）：**

```bash
# 如未安装 uv，先执行：
pip install uv
```

**编辑器配置（以 Kiro 为例，编辑 `~/.kiro/settings/mcp.json`）：**

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
      }
    }
  }
}
```

> 其他编辑器（Claude Desktop、Cursor、Antigravity、OpenAI Codex）的配置方式请参阅 [README.md](https://github.com/WaterTian/wechat-devtools-mcp#%EF%B8%8F-%E7%BC%96%E8%BE%91%E5%99%A8%E9%85%8D%E7%BD%AE)。

**两个必填环境变量：**

| 变量 | 说明 | 示例 |
|------|------|------|
| `WECHAT_DEVTOOLS_CLI` | 微信开发者工具 CLI 可执行文件路径 | `C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat` |
| `WECHAT_PROJECT_PATH` | 小程序项目绝对路径 | `D:\MyProjects\mini-app` |

---

### Step 1：运行时环境检查

| 检查项 | 验证方式 | 失败时操作 |
|--------|---------|--------------|
| 微信开发者工具已安装 | `wechat_ide(action='status')` → `cli_exists: true` | 安装工具并设置 `WECHAT_DEVTOOLS_CLI` 环境变量 |
| 项目路径已配置 | `wechat_ide(action='status')` → `project_exists: true` | 设置 `WECHAT_PROJECT_PATH` 环境变量 |
| 已登录微信账号 | `wechat_ide(action='is_login')` → `logged_in: true` | 调用 `wechat_ide(action='login')` 扫码 |
| Node.js 已安装 | status → `node_available: true` | 安装 Node.js ≥ 8.0 |

> **环境诊断命令**：不确定当前环境状态时，首先调用 `wechat_ide(action='status')` 获取完整诊断报告，一次性确认所有前置条件。

---

## 能力映射字典

### `wechat_ide` — IDE 生命周期

| action | 功能 | 关键参数 |
|--------|------|---------:|
| `open` | 打开 IDE/项目 | `project_path?`, `cdp_enabled=true` |
| `login` | 扫码登录 | `qr_format="terminal"` |
| `is_login` | 检查登录状态 | 无 |
| `close` | 关闭项目窗口 | `project_path?` |
| `quit` | 退出 IDE | 无 |
| `status` | 环境诊断 | 无 |

### `wechat_build` — 构建与发布

| action | 功能 | 关键参数 |
|--------|------|---------:|
| `compile` | 编译检查（捕获错误/警告） | `project_path?` |
| `preview` | 生成预览二维码 | `qr_format="terminal"` |
| `upload` | 上传到微信后台 | **`version`（必填）**, `desc?` |
| `build_npm` | 构建 NPM 依赖 | 无 |
| `cache_clean` | 清除缓存 | `clean_type="compile"` |

### `wechat_automator` — 自动化交互（13 个 action）

> **前提**：先调用 `wechat_automator(action='start')` 开启自动化端口，**整个会话只需调用一次**。

| action | 功能 | 必填参数 |
|--------|------|---------:|
| `start` | 开启自动化端口 | `project_path?` |
| `tap` | 点击元素 | **`selector`** |
| `input` | 输入文本 | **`selector`**, **`value`** |
| `element_info` | 获取元素详情（文本/尺寸/WXML） | **`selector`** |
| `set_data` | 热更新页面 data（无需重编译） | **`data_json`** |
| `call_method` | 调用页面方法 | **`method`** |
| `call_wx` | 调用 wx API | **`method`** |
| `mock_wx` | Mock wx API 返回值 | **`method`**, **`result_json`** |
| `evaluate` | 执行 JS 表达式（逻辑层） | **`expression`** |
| `page_stack` | 获取页面栈 | 无 |
| `page_data` | 获取当前页面 data | 无 |
| `system_info` | 获取运行时系统信息 | 无 |
| `storage` | 获取本地缓存 | `key?`（空=列出全部） |

### `wechat_inspector` — 运行时日志采集

| action | 功能 | 关键参数 |
|--------|------|---------:|
| `console` | automator 端口采集 console 日志和 JS 异常 | `duration=10`, `log_type="all"` |
| `cdp` | CDP 协议采集底层日志（WXML 警告/渲染层报错） | `duration=10`, `detail_level="concise"`, `max_logs=50` |

> **cdp 前提**：用 `cdp_enabled=true` 打开项目，确保端口 9222 可用。

### `wechat_screenshot` — 界面截图

| 参数 | 说明 |
|------|------|
| `output_path`（**必填**）| 截图保存路径（绝对路径），例如 `C:\tmp\shot.png` |
| `auto_port` | 自动化端口，默认 9420 |

> **前提**：需先调用 `wechat_automator(action='start')` 开启自动化端口。

### `wechat_navigate` — 跳转并采集日志

| 参数 | 说明 |
|------|------|
| `page_path`（**必填**）| 页面路径，例如 `pages/index/index` |
| `wait_ms` | 等待时间（毫秒），默认 2000，建议 3000 |
| `detail_level` | `concise`（仅 errors+warnings）或 `full` |
| `max_logs` | 最大返回条数，默认 50 |

> **前提**：需先调用 `wechat_automator(action='start')` 并以 `cdp_enabled=True` 打开项目。

### `wechat_file` — 项目文件读取

| action | 功能 | 必填参数 |
|--------|------|---------:|
| `project_info` | 项目完整信息（config + app.json + 目录结构） | 无 |
| `list_pages` | 页面列表（含文件完整性检查） | 无 |
| `read_page` | 读取页面源码（.wxml/.wxss/.js/.json 全套） | **`page_path`** |
| `read_file` | 读取任意单个文件（最多 800 行） | **`file_path`** |

### `wechat_cloud` — 云函数管理

| action | 功能 | 必填参数 |
|--------|------|---------:|
| `env_list` | 列出云环境 | 无 |
| `func_list` | 列出云函数 | **`env`** |
| `func_info` | 获取云函数详情 | **`env`**, **`names`** |
| `func_deploy` | 上传云函数 | **`env`** |
| `func_download` | 下载云函数 | **`env`**, **`name`**, **`download_path`** |

---

## SOP 标准操作流程

### SOP A：项目初始化（新环境必做）

```
1. wechat_ide(action='status')                        # 一次性诊断所有环境项
2. wechat_ide(action='is_login')                      # 确认登录状态
   ↳ 如未登录: wechat_ide(action='login', qr_format='terminal')  # 扫码登录
3. wechat_ide(action='open', cdp_enabled=True)        # 开启 IDE + CDP 端口 9222
4. wechat_automator(action='start')                   # 开启自动化端口 9420
   ↳ 等待 3 秒再继续后续操作
5. wechat_file(action='project_info')                 # 可选：获取项目结构全貌
```

### SOP B：UI 调试（数据/布局问题）

```
1. wechat_navigate(page_path='pages/xxx/xxx', wait_ms=3000)
   ↳ 跳转页面，同步采集 CDP 日志（concise 模式，仅 errors+warnings）
2. wechat_screenshot(output_path='C:\tmp\debug.png')  # 截图查看当前布局
3. wechat_automator(action='page_data')               # 查看响应式 data 状态
4. [如发现数据异常] wechat_automator(action='set_data', data_json='{"key": "val"}')
   ↳ 热更新 data 验证 UI 响应（无需重编译）
5. [如需确认元素] wechat_automator(action='element_info', selector='.target')
   ↳ 获取元素文本/尺寸/WXML 结构
```

### SOP C：异常排查（报错/白屏/JS 异常）

```
1. wechat_inspector(action='cdp', duration=5, detail_level='concise')
   ↳ 快速获取 errors/warnings 摘要，控制 Token 消耗
   ↳ summary.errors > 0 → 重新调用 detail_level='full' 查看完整上下文
2. wechat_inspector(action='console', duration=5, log_type='exception')
   ↳ 补充获取 JS 异常堆栈
3. wechat_file(action='read_page', page_path='pages/xxx/xxx')
   ↳ 根据 source 字段定位源码文件，读取相关代码
4. wechat_build(action='compile')
   ↳ 触发编译，捕获静态错误和 warning
```

### SOP D：全页面巡检（回归/发布前验收）

```
1. wechat_file(action='list_pages')                   # 获取所有页面路径列表

2. 对每个 page 依次顺序执行（禁止并行）：
   a. wechat_navigate(page_path=page, wait_ms=3000)
      ↳ 跳转 + 采集 CDP 日志（返回 summary）
   b. wechat_screenshot(output_path=f'C:\tmp\{page_name}.png')
      ↳ 截图保存

3. 汇总所有页面的 summary.errors 和 summary.warnings
   ↳ 按严重程度排序，输出完整巡检报告
```

### SOP E：Mock 集成测试（支付/权限/设备）

```
1. 完成 SOP A 初始化
2. 调用所需 Mock：
   wechat_automator(action='mock_wx', method='requestPayment', result_json='{"errMsg": "requestPayment:ok"}')
   wechat_automator(action='mock_wx', method='getUserProfile', result_json='{"userInfo": {"nickName": "测试用户"}}')
3. 触发 UI 交互：
   wechat_automator(action='tap', selector='.pay-btn')
4. 验证结果：
   wechat_automator(action='page_data')              # 检查 data 变化
   wechat_screenshot(output_path='C:\tmp\mock_result.png')  # 截图确认
```

> **注意**：Mock 仅在当前自动化会话中有效，重启开发者工具需重新设置。

---

## CDP 日志渐进排查策略

```
第一次查看 → detail_level='concise'（仅 errors + warnings，节省 Token）
                   ↓ summary.errors > 0？
                  是 → detail_level='full'（获取完整日志和 source 定位）
                  否 → 问题不在渲染层，切换到 console 采集

日志过多时 → max_logs=20，聚焦最严重的前 N 条（优先级：error > warning > info）
需要定位源码 → 读取 log.source 字段 → wechat_file(action='read_file', file_path=source)
```

| 场景 | 推荐参数组合 |
|------|------------|
| 快速诊断 | `duration=5, detail_level='concise', max_logs=20` |
| 深度排查 | `duration=10, detail_level='full', max_logs=100` |
| 页面巡检 | `duration=3, detail_level='concise', max_logs=30` |

---

## 返回值格式（统一 JSON 信封）

```json
// 成功
{"success": true, "data": {...}, "message": "操作描述"}

// 失败（含修复提示）
{"success": false, "error_code": "PARAM_MISSING", "message": "缺少参数", "hint": "补充修复提示"}
```

**常见 error_code 与处理方式：**

| error_code | 含义 | 处理方式 |
|------------|------|----------|
| `PARAM_MISSING` | 必填参数未提供 | 查看 hint 字段，补充对应参数后重试 |
| `CLI_NOT_FOUND` | 找不到微信开发者工具 CLI | 检查 `WECHAT_DEVTOOLS_CLI` 环境变量 |
| `PROJECT_PATH_MISSING` | 项目路径未配置 | 检查 `WECHAT_PROJECT_PATH` 环境变量 |
| `NODE_NOT_FOUND` | Node.js 未安装 | 安装 Node.js ≥ 8.0 并确保在 PATH 中 |
| `CLI_TIMEOUT` | CLI 执行超时 | 检查 IDE 服务是否正常运行，重启 IDE |

---

## 高级使用场景

### 场景一：热调试（不重启验证 UI 变化）

```
wechat_automator(action='set_data', data_json='{"list": [], "loading": false}')
→ 立即生效，无需重编译
→ wechat_screenshot 截图验证
```

### 场景二：页面方法触发

```
# 调用当前页面的 fetchData 方法
wechat_automator(action='call_method', method='fetchData', args_json='[]')

# 调用带参数的方法
wechat_automator(action='call_method', method='onItemClick', args_json='[{"id": 123}]')
```

### 场景三：全局状态读取

```
# 读取 globalData
wechat_automator(action='evaluate', expression='getApp().globalData')

# 读取当前页面实例
wechat_automator(action='evaluate', expression='getCurrentPages()[0].data')
```

### 场景四：Storage 调试

```
# 列出所有 key
wechat_automator(action='storage')

# 读取特定 key
wechat_automator(action='storage', key='userToken')
```

### 场景五：云函数快速部署

```
1. wechat_cloud(action='env_list')                        # 确认云环境 ID
2. wechat_cloud(action='func_list', env='prod-xxx')       # 查看现有函数
3. wechat_cloud(action='func_deploy', env='prod-xxx', names=['myFunc'])  # 部署指定函数
4. wechat_cloud(action='func_info', env='prod-xxx', names=['myFunc'])    # 验证部署结果
```

---

## 常见故障排查

### CDP 采集失败（9222 端口未绑定）

**原因**：开发者工具已有实例运行，`--remote-debugging-port` 参数被忽略。

**解决**：不要手动启动开发者工具。直接调用：
```
wechat_ide(action='open', cdp_enabled=True)
```
这会自动 kill 已有进程并以 CDP 模式重新启动。

### 自动化操作失败（元素未找到）

**原因**：元素可能不在当前页面，或 selector 不正确。

**解决**：
```
1. wechat_automator(action='page_stack')   # 确认当前页面路径
2. wechat_automator(action='element_info', selector='.target')  # 验证选择器
3. 如需跳转：wechat_navigate(page_path='...')
```

### CLI 超时（`CLI_TIMEOUT`）

**原因**：IDE 服务未运行，或 IDE HTTP 端口未开启。

**解决**：
```
1. wechat_ide(action='status')   # 诊断 CLI 连接状态
2. wechat_ide(action='open')     # 重新打开 IDE
3. 等待 5 秒后重试操作
```
> 单次对话中对同一失败操作**最多重试 3 次**，超出则向用户反馈并请求人工干预。

### 截图为空白或尺寸为 0

**原因**：自动化端口未开启，或页面还未渲染完成。

**解决**：
```
1. 确认已调用 wechat_automator(action='start')
2. 等待至少 2 秒后再截图
3. 如用 navigate 跳转，增加 wait_ms=3000
```

---

## 绝对红线

- **禁止**在未确认 `is_login: true` 的情况下调用 `preview` / `upload`
- **禁止**对生产项目调用 `cache_clean(clean_type='all')`，会清空所有缓存数据
- **禁止**在 `evaluate` 中执行 `eval()` 或发起网络请求等不安全代码
- **禁止**脑补小程序运行状态，必须以 MCP 接口返回的实际 DOM 结构和数据为准
- **必须**在 `wechat_screenshot` 中提供完整绝对路径 `output_path`
- **必须**先调用 `wechat_automator(action='start')` 再使用任何自动化和截图功能
- **必须**在执行 UI 操作（tap/input）前，先用 `element_info` 确认元素存在
- **禁止**对同一失败操作进行超过 3 次重试，应转而诊断根因
