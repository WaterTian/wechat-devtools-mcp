# Windows 适配实现说明（2.x 静态解包核对）

> 2026-09-04：先对官方 Stable **2.02.2608060 win32_x64** 安装包（NSIS 自解压，190 MB，解包 790 MB）
> 用 7-Zip 在 macOS 上静态核对，当天再在 **Windows 11 真机**跑 `tests/manual/smoke_ide.py`（4 轮 19/19，最终 a160e4f）。
> 真机耗时：`open` 7.7~9.6s、`start` 9.5s、`compile` 14.4s、`quit` 4.0s（等到进程退出）。
> macOS 对照见 [macos-internals.md](./macos-internals.md)。
>
> ⚠ 目录布局、文件名、状态文件均为开发者工具的**内部实现细节，官方未作承诺**；代码中的相关读取都必须能优雅回退。

## 安装根布局

```
<root>\                                  默认 %ProgramFiles(x86)%\Tencent\微信web开发者工具
│                                        （官方 install-root.mjs 的回退路径；注册表 App Paths 优先）
├── 微信开发者工具.exe                    Electron 主程序，202 MB，根目录唯一 > 50 MB 的 exe
├── wxfilewatcher.exe / wxfilewatcher_x64.exe   文件监听 helper
├── cli.bat                              旧 CLI 入口（仍保留）→ resources\app.asar.unpacked\js\common\cli\index.js
├── wechatidecli.cmd                     旧 CLI 别名，与 cli.bat 同逻辑
├── wechatide.cmd                        官方 skill / MCP bridge 入口 → js\common\cli\skill-index.js
├── cli.js
├── resources\
│   ├── app.asar                         213 MB；package.json: name = productName = 微信开发者工具，
│   │                                    version 2.02.2608060，main js/electron/main.js
│   ├── app.asar.unpacked\               package.json（version 2.02.2608060）
│   │   ├── js\common\cli\{index,skill-index,skill-error-rules,skill-outcome}.js
│   │   └── wechatide-skill\             自带 skill 0.3.9（与 macOS 同版）
│   └── default_app.asar / vsextensions\ / inspector_overlay\
├── locales\  *.pak  *.dll  icudtl.dat   Electron 36.6 / Chromium 136 运行时
└── 卸载微信开发者工具.exe.nsis
```

**NW.js 痕迹全部消失**：`code\package.nw`、`wechatdevtools.exe`、`node.exe` / `node-18.exe` 均不存在。

## 三个包装脚本怎么找主程序

`cli.bat` / `wechatidecli.cmd` / `wechatide.cmd` 是同一套逻辑：

```bat
chcp 65001                              ← 切 UTF-8
for %%F in (*.exe) do (排除 node.exe / node-18.exe / wxfilewatcher*.exe /
                       notification_helper.exe / wechatdevtools.exe，取 > 50 MB 的那个) → ELECTRON
set ELECTRON_RUN_AS_NODE=1
"%ELECTRON%" -e "<bootstrap>" "<cli 入口>" %*
```

即官方自己也不写死主程序文件名，而是「根目录下唯一的大 exe」。与 macOS 的 `cli` 包装同构。

## 本项目对应处理（`tools/ide.py` / `core/ide_state.py`）

| 事项 | 结论 | 状态 |
|------|------|------|
| 1.x / 2.x 判定 | `_resolve_windows_ide_executable`：`resources\app.asar.unpacked\package.json` 存在 → `electron`；`code\package.nw` → `nwjs`；都没有 → 旧字符串替换（`win32`） | ✅ 静态核对 |
| 主程序文件名 | 候选表首位 `微信开发者工具.exe` 命中；`wechatwebdevtools.exe` / `wechatdevtools.exe` 保留为备选以防改名 | ✅ 静态核对 |
| kill | `taskkill /F /IM 微信开发者工具.exe`：Electron 各子进程同镜像名，一并结束 | ✅ 静态核对 |
| 旧 CLI | `cmd /c <root>\cli.bat …` 路径与 1.x 一致，`WECHAT_DEVTOOLS_CLI` 默认值无需改 | ✅ 静态核对 |
| 用户数据目录 | **真机纠正静态推断**：实际在 `%LOCALAPPDATA%\微信开发者工具\User Data\<hash>\Default\{.ide,.cli,.ide-status}`，比 1.x 多一层 `User Data`，且在 Local 而非 Roaming。`ide_state` 已对每个候选根同时尝试有 / 无 `User Data` 两层 | ✅ 真机 |
| `.ide` 端口的可信度 | **2.x Windows 下 stale**：实例重启后不更新，只反映最近一次「服务端口开启」动作的端口。因此 Windows Electron 的 `open` 不再拿它当就绪判据，改为「CDP 已监听 + `/json/list` 出现 IDE 外壳 target」，真实连通性由 `cli open` 兜底（CLI 自带服务发现） | ✅ 真机 |
| `--remote-debugging-port` | app.asar 中零引用，由 Chromium 原生处理，与 macOS 相同 | ✅ 真机 |
| 两步式 open（带 CDP 直启 → `cli open --project`） | 与 macOS 一致，`cdp_ready` / `project_opened` 均 true | ✅ 真机 |

## 真机补充发现（2026-09-04，Windows 11）

- CDP 启动健康检查在 Windows 2.x 多两类噪音：`inspectee MPPage`（扩展注入的 inspectee 命令错误，原始日志 url 是 appservice、
  不带 `ide:///extensions/`，只能按 message 过滤）与 `access_token expired`（登录过期是环境状态，不是启动致命错误）。
  两者已加入 `STARTUP_NOISE_PATTERNS`，只影响 `open` 的健康检查，不影响 `inspector` / `navigate`。
- `wechat_ide(quit)` 与 `_kill_existing_ide` 在 Windows 用 `tasklist /FI "IMAGENAME eq 微信开发者工具.exe" /NH /FO CSV` 轮询，
  按行首引号判定命中（中文 Windows 控制台是 GBK，按 UTF-8 解码匹配中文镜像名会永远不命中而误报「已退出」）。
- 无人值守 `open`（计划任务在桌面会话拉起 IDE）未遇到 SmartScreen / 防火墙弹窗。
