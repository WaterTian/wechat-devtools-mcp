# 🛠️ MCP 工具箱完整文档

本项目提供 **44 个** MCP 工具，覆盖小程序全生命周期。

通过环境变量 `WECHAT_TOOLS_PRESET` 控制开放范围：
- `core`（默认）：18 个核心工具，覆盖 SOP 开发迭代和全页面巡检两个流程
- `full`：开放全部 44 个工具

标注说明：🟢 core + full 均可用 / 🔵 仅 full 可用

---

## 目录

1. [项目感知与上下文 (Context)](#1-项目感知与上下文-context)
2. [构建、预览与编译 (Build)](#2-构建预览与编译-build)
3. [自动化交互 (Automation)](#3-自动化交互-automation)
4. [实时调试与日志 (Debug)](#4-实时调试与日志-debug)
5. [云开发管理 (Cloud)](#5-云开发管理-cloud)
6. [系统诊断与管理 (System)](#6-系统诊断与管理-system)
7. [Mock 场景示例](#7-mock-场景示例)

---

## 1. 项目感知与上下文 (Context)

### 🟢 `wechat_project_info`

获取项目完整信息，包括 `project.config.json`、`app.json`、`app.wxss`、`app.js` 及目录结构概览。AI 开始开发前应优先调用。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

### 🟢 `wechat_list_pages`

列出 `app.json` 中所有注册页面，并检查每个页面的 `.wxml/.wxss/.js/.json/.ts` 文件是否存在。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

### 🟢 `wechat_read_page`

一键读取指定页面的全部源码文件（`.wxml`、`.wxss`、`.js`、`.json`），每个文件最多 500 行。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 页面路径，例如 `pages/index/index` |
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

### 🟢 `wechat_read_file`

读取项目中任意单个文件，最多 800 行。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file_path` | string | **必填** | 相对项目根目录的路径，例如 `app.json` |
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

## 2. 构建、预览与编译 (Build)

### 🟢 `wechat_compile_check`

**[最常用]** 触发编译并捕获所有 Error 和 Warning。AI 修改代码后应立即调用此工具验证。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `info_output` | string | null | 编译信息输出 JSON 文件路径 |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🟢 `wechat_preview_page`

快捷预览指定页面，自动构建 `compile_condition`，生成预览二维码（默认 base64 格式）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 要预览的页面路径，例如 `pages/index/index` |
| `query` | string | null | 页面参数，例如 `id=123&type=detail` |
| `qr_format` | string | `base64` | 二维码格式：`terminal`、`image`、`base64` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_preview`

预览小程序，支持自定义编译条件和二维码输出路径。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `qr_format` | string | `base64` | 二维码格式：`terminal`、`image`、`base64` |
| `qr_output` | string | null | 二维码输出文件路径 |
| `info_output` | string | null | 编译信息输出 JSON 文件路径 |
| `compile_condition` | string | null | 自定义编译条件（JSON 字符串），例如 `{"pathName":"pages/index/index","query":"x=1"}` |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

---

### 🔵 `wechat_build_npm`

构建小程序 NPM 依赖。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `compile_type` | string | null | 编译类型：`miniprogram` 或 `plugin` |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_upload`

上传代码至微信后台。⚠️ 会覆盖相同版本号的已有代码，请谨慎使用。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version` | string | **必填** | 版本号，例如 `1.0.0` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `desc` | string | null | 版本描述信息 |
| `info_output` | string | null | 上传信息输出 JSON 文件路径 |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

---

### 🔵 `wechat_cache_clean`

清除微信开发者工具的缓存。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `clean_type` | string | `compile` | 缓存类型：`storage`、`file`、`compile`、`auth`、`network`、`session`、`all` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_reset_fileutils`

重建工具内部文件缓存，重新监听项目文件。AI 修改大量文件后调用，确保开发者工具检测到所有变更。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

## 3. 自动化交互 (Automation)

> **前提**：需先调用 `wechat_auto` 开启 9420 自动化端口，**只需运行一次**。

### 🟢 `wechat_auto`

开启小程序自动化功能，监听指定端口，供后续自动化工具连接。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `auto_account` | string | null | 指定使用的 openid |
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

### 🔵 `wechat_tap_element`

通过 CSS 选择器定位页面元素并模拟点击（tap）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `selector` | string | **必填** | CSS 选择器，例如 `.submit-btn`、`#login` |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_input_element`

向 `input` 或 `textarea` 元素输入文本内容。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `selector` | string | **必填** | input/textarea 的 CSS 选择器 |
| `value` | string | **必填** | 要输入的文本内容 |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_set_page_data`

**热更新**：直接修改当前页面的响应式 data，无需重新编译即可刷新 UI。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data_json` | string | **必填** | 要设置的数据（JSON 字符串），例如 `{"message": "hello", "count": 42}` |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_get_page_data`

读取当前活跃页面的 data 模型状态，用于诊断数据绑定不生效等问题。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_call_page_method`

调用当前页面中的指定方法（如 `onPullDownRefresh`、自定义业务方法等）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `method` | string | **必填** | 要调用的页面方法名，例如 `onPullDownRefresh` |
| `args_json` | string | null | 方法参数（JSON 数组字符串） |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_get_element_info`

获取页面元素的详细信息（文本、WXML 结构、尺寸、位置、样式）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `selector` | string | **必填** | CSS 选择器 |
| `style_prop` | string | null | 要查询的具体 CSS 属性名，例如 `color` |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_mock_wx_method`

覆盖 `wx` 对象上指定方法的调用结果（Mock）。详见 [Mock 场景示例](#7-mock-场景示例)。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `method` | string | **必填** | 要 mock 的 wx 方法，例如 `showModal`、`chooseLocation` |
| `result_json` | string | **必填** | Mock 返回值（JSON 字符串），例如 `{"confirm": true}` |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_call_wx_method`

直接调用 `wx` 对象上的指定方法。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `method` | string | **必填** | wx 方法名，例如 `getStorageSync`、`setNavigationBarTitle` |
| `args_json` | string | null | 参数（JSON 数组字符串） |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_get_page_stack`

获取当前小程序的页面栈信息，包括每个页面的路径和查询参数。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_evaluate_expression`

在小程序逻辑层运行环境中直接执行一段 JS 表达式并返回结果。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expression` | string | **必填** | 要执行的 JS 表达式，例如 `getApp().globalData` |
| `auto_port` | int | `9420` | 自动化端口 |

---

### 🔵 `wechat_run_automation_script`

执行自定义 JS 自动化测试脚本（Node.js CommonJS 模块格式），并捕获执行期间的所有日志和异常。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `script_content` | string | **必填** | JS 脚本内容，必须导出接收 `miniProgram` 参数的 async function |
| `auto_port` | int | `9420` | 自动化端口 |
| `timeout` | int | `30` | 脚本执行超时时间（秒），范围 5~300 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

脚本格式示例：

```js
module.exports = async function(miniProgram) {
  const page = await miniProgram.navigateTo('/pages/index/index');
  await page.waitFor(1000);
  const el = await page.$('.my-button');
  if (el) await el.tap();
  return { tapped: true };
};
```

---

### 🔵 `wechat_auto_replay`

打开自动化测试窗口，可回放之前录制的测试用例。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `replay_all` | bool | `false` | 是否回放全部测试用例 |
| `project_path` | string | 环境变量 | 小程序项目路径 |

---

## 4. 实时调试与日志 (Debug)

### 🟢 `wechat_get_cdp_logs`

**[推荐]** 通过 Chromium DevTools Protocol (CDP) 采集高清日志。能捕获 `wechat_get_console_logs` 无法获取的底层信息：WXML 语法警告、废弃 API 提示（如 `wx.getSystemInfoSync`、`wx.saveFile`）、渲染层网络报错等。

> **前提**：调用 `wechat_open` 时必须设置 `cdp_enabled=true`，确保端口 9222 未被占用。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `port` | int | `9222` | CDP 端口 |
| `verbose` | bool | `false` | `true` 时返回全量日志，不过滤系统日志 |

---

### 🟢 `wechat_get_console_logs`

实时采集小程序运行时的 console 日志和 JS 异常，支持采集期间自动触发点击操作。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `log_type` | string | `all` | 监听类型：`all`（日志+异常）、`console`（仅日志）、`exception`（仅异常） |
| `tap_selector` | string | null | 采集期间自动点击的 CSS 选择器，例如 `.btn` |
| `tap_delay` | int | `500` | 点击延迟（毫秒），开始采集后等待多久再触发点击 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

---

### 🟢 `wechat_get_exceptions`

专门监听小程序运行时 JS 异常（exception 事件），输出比 `wechat_get_console_logs` 更清晰的异常信息，包含完整调用栈。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `duration` | int | `10` | 采集持续时间（秒），范围 1~120 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

---

### 🟢 `wechat_capture_screenshot`

捕获当前小程序模拟器的界面截图，默认支持截取长图（自动滚动并拼接），保存为 PNG 文件。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | string | **必填** | 截图保存路径（绝对路径），例如 `D:/screenshots/page.png` |
| `auto_port` | int | `9420` | 自动化端口 |
| `overlap` | int | `50` | 分段重叠像素数，防止内容截断 |

---

### 🟢 `wechat_navigate_and_capture`

跳转到指定页面，等待指定时间，捕获该时间窗口内的所有 console 日志和 JS 异常。适合检查页面初始化（`onLoad`、`onShow`）阶段的日志。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page_path` | string | **必填** | 要跳转的页面路径，例如 `pages/index/index` |
| `wait_ms` | int | `2000` | 跳转后等待时间（毫秒），范围 100~30000 |
| `auto_port` | int | `9420` | 自动化监听端口 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

---

### 🔵 `wechat_get_system_info`

通过自动化接口获取小程序运行时的系统信息（基础库版本、平台、屏幕尺寸等）。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_port` | int | `9420` | 自动化监听端口 |
| `project_path` | string | null | 小程序项目路径（仅用于提示） |

---

### 🔵 `wechat_get_storage`

获取小程序的本地缓存数据。不提供 `key` 时返回所有已占用的 key 列表及空间统计。

> **前提**：需先调用 `wechat_auto` 开启自动化端口。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `key` | string | null | 要读取的 Storage key；为空则列出所有 key |
| `auto_port` | int | `9420` | 自动化端口 |

---

## 5. 云开发管理 (Cloud)

### 🔵 `wechat_cloud_env_list`

列出小程序关联的所有云开发环境。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

---

### 🔵 `wechat_cloud_func_list`

查看指定云环境下的线上云函数列表。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `env` | string | **必填** | 云环境 ID |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_cloud_func_info`

查看指定云函数的详细信息。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `env` | string | **必填** | 云环境 ID |
| `names` | list[string] | **必填** | 云函数名称列表 |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_cloud_func_deploy`

上传云函数到指定云环境。可通过 `names`（函数名）或 `paths`（绝对路径）指定目标函数。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `env` | string | **必填** | 云环境 ID |
| `names` | list[string] | null | 云函数名称列表（配合 `project_path` 使用） |
| `paths` | list[string] | null | 云函数目录绝对路径列表 |
| `remote_npm_install` | bool | `false` | `true` 时云端安装依赖，不上传 `node_modules` |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_cloud_func_download`

从云环境下载指定云函数到本地目录。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `env` | string | **必填** | 云环境 ID |
| `name` | string | **必填** | 云函数名称 |
| `download_path` | string | **必填** | 下载后的存放位置路径 |
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |

---

## 6. 系统诊断与管理 (System)

### 🟢 `wechat_setup_sop`

**[推荐]** 一键完成初始化 SOP，自动依次执行：`wechat_is_login` → `wechat_auto` → `wechat_open` → `wechat_project_info`。任一步骤失败后仍继续执行后续步骤，减少工具调用轮次和 token 消耗。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `auto_port` | int | `9420` | 自动化端口 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |
| `cdp_enabled` | bool | `false` | 是否开启 CDP 调试端口（9222） |

---

### 🟢 `wechat_open`

打开微信开发者工具 IDE，或打开指定的小程序项目（每次执行都会自动编译刷新）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径；不提供则仅启动 IDE |
| `cdp_enabled` | bool | `false` | 是否开启 Chromium 调试端口（9222），开启后可捕获完整 WXML 警告 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言：`en` 或 `zh` |

---

### 🔵 `wechat_login`

登录微信开发者工具，生成二维码供扫码登录。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `qr_format` | string | `terminal` | 二维码格式：`terminal`、`image`、`base64` |
| `qr_output` | string | null | 二维码输出文件路径 |
| `result_output` | string | null | 登录结果输出文件路径（JSON 格式） |
| `port` | int | null | IDE HTTP 服务端口号 |
| `lang` | string | null | 界面语言 |

---

### 🟢 `wechat_is_login`

检查微信开发者工具当前是否已登录。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 小程序项目路径 |
| `appid` | string | null | 小程序 AppID |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🟢 `wechat_get_status`

返回 MCP 服务的运行状态和当前项目配置信息，包括 CLI 路径、项目路径及当前账号状态。无需参数。

---

### 🟢 `wechat_list_tools`

列出所有已注册的 MCP 工具及其分类。无需参数。

---

### 🔵 `wechat_close_project`

关闭微信开发者工具中指定的项目窗口。注意：关闭时 IDE 会弹窗确认，3 秒后自动关闭。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | string | 环境变量 | 要关闭的小程序项目路径 |
| `port` | int | null | IDE HTTP 服务端口号 |

---

### 🔵 `wechat_quit_ide`

关闭整个微信开发者工具。⚠️ 这将关闭 IDE 及所有打开的项目。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `port` | int | null | IDE HTTP 服务端口号 |

---

## 7. Mock 场景示例

`wechat_mock_wx_method` 可覆盖 `wx` 对象上指定方法的返回值，让 AI 在无需真实设备权限或支付环境的情况下，模拟各类原生 API 的回调结果，用于自动化测试和功能验证。

> **注意**：Mock 仅在当前自动化会话中有效，重启开发者工具或重新调用 `wechat_auto` 后会自动失效，需重新设置。

### result_json 参数说明

`result_json` 是一个 JSON 字符串，其内容对应目标 wx API `success` 回调函数接收到的参数对象。

| 字段 | 所属 API | 说明 |
|------|----------|------|
| `errMsg` | 通用 | 成功时格式为 `"apiName:ok"`，失败时包含原因，例如 `"apiName:fail cancel"` |
| `confirm` | `showModal` | 用户是否点击了确认按钮 |
| `cancel` | `showModal` | 用户是否点击了取消按钮 |
| `name` | `chooseLocation` | 位置名称 |
| `address` | `chooseLocation` | 详细地址 |
| `latitude` | `chooseLocation` | 纬度（浮点数） |
| `longitude` | `chooseLocation` | 经度（浮点数） |
| `tempFilePaths` | `chooseImage` | 选中图片的临时文件路径数组 |
| `tempFiles` | `chooseImage` | 选中图片的文件对象数组（含 `path` 和 `size`） |

---

### 场景一：支付成功

模拟 `wx.requestPayment` 调用成功，触发页面的支付成功逻辑分支：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "requestPayment",
    "result_json": "{\"errMsg\": \"requestPayment:ok\"}"
  }
}
```

### 场景二：支付失败（用户取消）

> `fail cancel` 是微信支付用户取消时的标准 `errMsg` 格式，页面代码通常通过 `fail` 回调或 `errMsg.includes('cancel')` 来判断。

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "requestPayment",
    "result_json": "{\"errMsg\": \"requestPayment:fail cancel\"}"
  }
}
```

### 场景三：弹窗确认（showModal）

模拟用户点击了确认按钮：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "showModal",
    "result_json": "{\"confirm\": true, \"cancel\": false, \"errMsg\": \"showModal:ok\"}"
  }
}
```

### 场景四：定位授权（chooseLocation）

模拟用户选择了一个位置，返回完整的位置信息：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "chooseLocation",
    "result_json": "{\"name\": \"腾讯北京总部\", \"address\": \"北京市海淀区科学院南路2号\", \"latitude\": 39.9842, \"longitude\": 116.3093, \"errMsg\": \"chooseLocation:ok\"}"
  }
}
```

### 场景五：相册选择（chooseImage）

模拟用户从相册选择了两张图片，返回临时文件路径：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "chooseImage",
    "result_json": "{\"tempFilePaths\": [\"wxfile://tmp_photo_001.jpg\", \"wxfile://tmp_photo_002.jpg\"], \"tempFiles\": [{\"path\": \"wxfile://tmp_photo_001.jpg\", \"size\": 102400}, {\"path\": \"wxfile://tmp_photo_002.jpg\", \"size\": 204800}], \"errMsg\": \"chooseImage:ok\"}"
  }
}
```

### 场景六：获取用户信息（getUserProfile）

模拟用户授权并返回基本信息：

```json
{
  "tool": "wechat_mock_wx_method",
  "arguments": {
    "method": "getUserProfile",
    "result_json": "{\"userInfo\": {\"nickName\": \"测试用户\", \"avatarUrl\": \"https://example.com/avatar.png\", \"gender\": 1, \"country\": \"China\", \"province\": \"Guangdong\", \"city\": \"Shenzhen\"}, \"errMsg\": \"getUserProfile:ok\"}"
  }
}
```

---

*返回 [README](./README.md)*
