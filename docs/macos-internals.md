# macOS 适配实现说明（真机实测）

> 本文记录 MCP 在 macOS 上启动 IDE、连接 CDP 所依赖的开发者工具内部结构，
> 供调试本项目与后续 Linux 适配参考。用户侧配置见 README「macOS」示例。
>
> ⚠ 文中涉及的目录布局、进程名、端口落盘文件均为**开发者工具的内部实现细节，
> 官方未作任何承诺**，可能随版本变化。代码中所有相关读取都必须能优雅回退。

## 版本格局（决定「必须双轨」）

| 渠道 | 版本 | 运行时 |
|------|------|--------|
| Stable 稳定版 | 1.06.x | **NW.js**（Chromium 91） |
| RC 预发布 | 1.06.x | NW.js |
| Nightly 开发版 | 1.06.x | NW.js 0.54.1 |
| **Nightly Electron Build** | **2.02.x** | **Electron 36.6.0 / Chromium 136** |

2.x 是官方「全新改版」的开发者预览版，明确改用 Electron 实现跨平台；1.06.x 仍是 Stable。
**因此启动路径必须同时支持两代，不能替换。**

---

## 一、IDE 1.x（NW.js）——2026-04-29 实证

- NW.js Framework 位于 `Contents/Frameworks/nwjs Framework.framework/`（Chromium 91），标准 Chromium flag（`--remote-debugging-port`）可用，额外 args 透传给 package.nw 内部 JS
- GUI 主程序入口是 `Contents/MacOS/wechatdevtools`（224KB loader）；`wechatwebdevtools`（4.6MB）是 framework helper，**不是入口**
- 启动必须传 `Contents/Resources/package.nw` 作为参数
- `--project=<path>` 可直接透传，单步即可打开项目

### CDP targets（1.x）

- `http://127.0.0.1:<port>/__pageframe__/pages/...` — 渲染层 WXML
- `http://127.0.0.1:<port>/appservice/mainframe` — 逻辑层 appService
- `devtools://` / `chrome-extension://` / `background_page` — IDE 自身

---

## 二、IDE 2.x（Electron）——2026-08-20 实证（2.02.2607271）

### Bundle 结构

```
wechatwebdevtools.app/Contents/
├── Info.plist                    CFBundleExecutable = Electron，CFBundleIdentifier = com.github.Electron
├── MacOS/
│   ├── Electron                  ← 真正的 GUI 入口（69KB loader）
│   ├── wechatwebdevtools         4.4MB helper，不是入口
│   ├── cli                       bash wrapper，已改写为 Electron 版
│   └── cli.js
├── Frameworks/Electron Framework.framework/   Chromium 136.0.7103.177
└── Resources/
    ├── app.asar                  208MB，应用代码（package.json: version 2.02.2607271, main js/electron/main.js）
    └── app.asar.unpacked/        cli 入口在 js/common/cli/cli 实际路径下
```

**NW.js 痕迹已全部消失**：`MacOS/wechatdevtools`、`Resources/package.nw`、`Frameworks/nwjs Framework.framework` 均不存在。

`cli` wrapper 自身也重写了，用 `ELECTRON_RUN_AS_NODE=1 Electron -e <bootstrap> <cli entry>` 调起，文件里还留着注释掉的 NW.js 旧行。

### cdp_enabled 模式启动（两步式）

`--project=` **2.x 不再识别**（实测 CDP target 显示 `electron-project.html?projectpath=` 为空）。且 app.asar 内含 `requestSingleInstanceLock`，带新参数启动前必须先杀掉旧实例。正确姿势：

```bash
# 1. 先带 CDP 起进程（不传 --project）
/Applications/wechatwebdevtools.app/Contents/MacOS/Electron --remote-debugging-port=9222

# 2. 等 IDE 服务就绪后，用 CLI 让运行中的实例打开项目
/Applications/wechatwebdevtools.app/Contents/MacOS/cli open --project /path/to/miniprogram
```

- 入口名从 Info.plist 的 `CFBundleExecutable` 读，比硬编码更能跟上官方大版本变动
- 清理用 `pkill -9 -f "/Applications/wechatwebdevtools.app"`（**按 .app 包路径**）。
  旧模式 `pkill -f wechatdevtools` **匹配不到 2.x** —— `wechatwebdevtools` 里并不含 `wechatdevtools` 子串，
  一个进程都杀不到

### CDP targets（2.x，已载入项目）

| type | url | 处理 |
|------|-----|------|
| webview | `http://127.0.0.1:<port>/__pageframe__/pages/...` | ✅ 采集（渲染层，与 1.x 一致） |
| webview | `http://127.0.0.1:<port>/appservice/s0/_sessionId/<session>/mainframe` | ✅ 采集（逻辑层，**路径较 1.x 变化**） |
| webview | `devtools://devtools/bundled/devtools_app.html` | ❌ 排除（注意 type 是 **webview**，会从 `type !== 'webview'` 的旧规则缝里漏进来） |
| iframe | `chrome-extension://<id>/devtools/devtools.html` | ❌ 排除 |
| page | `file:///…/app.asar/html/electron-entrance.html` | ❌ 排除（**2.x 新增外壳页**） |
| page | `file:///…/app.asar/html/electron-project.html` | ❌ 排除（同上） |

**实测噪音占比**：修复前 6 秒采集 734 条，其中 448 条（61%）来自 file:// 外壳页、82 条来自 devtools://。
过滤后同场景 206 条，来源只剩 appservice 与 `__pageframe__`。

### 采集量与流上限（重要）

6 秒 CDP 采集的单条 NDJSON 响应实测 **649,766 字节（634.5 KiB）**，是 asyncio 默认流上限
64 KiB 的近 10 倍。`readline()` 会抛 `LimitOverrunError`，异常被吞掉后采集**恒返回 0 条**。
`node_bridge` 创建 daemon 时必须显式传 `limit=`（现为 16 MiB）。

### IDE 落盘的运行时状态（比猜端口可靠）

```
~/Library/Application Support/微信开发者工具/<32位hash>/Default/
    .ide         → 11071    IDE 服务端口，随每次启动刷新，CLI 也靠它找 IDE
    .cli         → 3799     CLI 端口
    .ide-status  → On       服务端口开关状态
```

多个 `<hash>` 目录会共存（不同版本/渠道各一份），取 `.ide` 最近写入的那个。
硬编码候选端口列表 `[39797, 11321, ...]` 实测**完全猜不中**（2.x 用的是 11071）。
注意这些属内部实现细节，官方未作承诺，读不到必须能回退。

### 已知噪音与「假噪音」

- 未登录时 IDE 启动会报 `localhost.weixin.qq.com:14013/api/check-login` 连接失败，登录后消失，非 MCP 问题
- ⚠ **`ide:///extensions/inject/...` 来源的 warning 不是噪音**：实测内容包括「无效的 app.json ["sharePolicy"]」
  「wx.getSavedFileInfo 即将废弃」「Some selectors are not allowed in component wxss」
  「IntersectionObserver is using slowest path」——都是真实的应用问题，**不要过滤**

---

## 三、跨平台代码规则

- `subprocess.CREATE_NO_WINDOW` 仅 Windows 存在，统一 `getattr(subprocess, "CREATE_NO_WINDOW", 0)` 兜底（测试 mock `sys.platform` 时直接引用会 AttributeError）
- Node 路径候选（`node_bridge.py`）：`/opt/homebrew/bin/node`（Apple Silicon）、`/usr/local/bin/node`（Intel）、nvm 路径。GUI 应用 spawn MCP 时 PATH 常不含 Homebrew
- 判定运行时用「`Resources/package.nw` 是否存在」：存在 → NW.js(1.x)，否则 → Electron(2.x)

## 四、待验证

- **Windows 侧 2.x**：`微信开发者工具.exe` 主程序名与 `wechatdevtools.exe` kill 模式在 2.x 上很可能同样失效，
  官方文档与社区均未给出 2.x 的 Windows 目录结构，缺 Windows 机无法验证。建议改为防御式探测
- **Linux 适配**：`_resolve_ide_executable_for_cdp` 对 linux 抛 `NotImplementedError`，有真机时按上述结构补
