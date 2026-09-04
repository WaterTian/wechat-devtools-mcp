# 版本历史

> 完整逐版本说明。README 只保留最近版本的一句话摘要。
> 英文版见 [CHANGELOG_EN.md](./CHANGELOG_EN.md)。

| 版本 | 说明 |
|------|------|
| **0.9.17** | **开发者工具 2.x Stable 适配 + evaluate 函数式签名 + 提效**（2026-09-03）：微信开发者工具 2.x 自 2026-08-18 起转为官方 Stable（1.06 下架），本版在 Stable 2.02.2608060 真机全量回归通过。**evaluate 新增 `fn_source`**（完整函数源码 + `args_json` 入参，与官方 `automation_evaluate` 同构），修复多语句 `expression` 静默只执行第一条的根因（本地先编译 `return (code)`，多语句必然 SyntaxError 才退回语句模式），返回 `mode`。**Windows 1.x/2.x 双轨判定**：按官方 install-root.mjs 的 `code\package.nw` / `resources\app.asar.unpacked` 探测点区分，Electron 走两步式 open（Windows 真机未验证）。**`status` 新增 `official_mcp`**：只读心跳探测 IDE 2.x 内建 MCP，可用时提示基础操作优先走官方、本项目专注长图截图 / CDP 结构化日志 / 任务级 SOP。**提效**：`open` 与 `compile` 改为按就绪信号等待（kill 后轮询进程消失、CDP 监听即止、等小程序 target 出现再采 3s、compile 后立即查 pageStack），真机 `open` 约 28s → 7.6s。**修复**：`open` 不传 `project_path` 时回退 `WECHAT_PROJECT_PATH`（此前 2.x 两步式第二步被跳过，项目全靠 IDE 会话恢复顺手打开）；compile 过滤新版 CLI 的 Node `punycode` 弃用提示噪音；`start` 端口不监听时重跑 `cli auto`（最多 3 轮，纯 CLI open 后窗口未加载完会假成功）；`quit` 等进程真正退出并返回 `exited`；automator 连不上 9420 时统一附恢复 hint；`call_method` 失败时错误信息带页面路径。**文档**：README 精简（490 → 167 行）、版本历史迁至本文件；SKILL / tool_reference 逐字段对照代码核对修正 15 处、删除全部版本号历史陈述；配置示例注册名改为 `wechat-devtools-mcp`（官方 IDE 2.x 把内建 bridge 注册成 `wechat-devtools`，同名会被覆盖）；新增「与官方能力的关系」章节。测试 214 → 250 项，另 4 个 JS 脚本 46 断言 |
| **0.9.16** | **长页面截图全面修复 + 源码开源**：固定区域识别由「找没变的」改为「找会动的」——旧判据逐行比对两张截图、「没变」即判为固定区，这要求固定元素**像素级稳定**，而半透明/毛玻璃导航栏会透出下方滚动内容、滚动时加阴影、状态栏还带跳变的时钟，任一情况都从第 0 行判负并返回 0，导航栏被当作内容拼进每一段。新判据利用两张图之间**已知的滚动距离**：能按 delta 找到对应行的即滚动内容，这是滚动内容的定义性特征、与它长什么样无关，因此不再依赖固定元素稳定，旧版为兼容而堆的 `MAX_GAP`、`SAFE_AREA_SKIP` 两个补丁一并删除（各自绑死了一种设备/设计假设）。合成用例对比（期望/旧/新）：半透明头 130/**0**/130、跳变时钟 140/**20**/140、纯色内容 100/**200**/100 —— 末项是此前未知的丢数据缺陷，纯色内容逐行「没变」被误判为固定区而整块吞掉。**修复长图停在前两屏**：`waitForScrollComplete` 旧实现连续两次读数相同即返回，`pageScrollTo` 尚未生效时两次读到的都是滚动前的位置，调用方据此判定「已到底部」直接停止（实测某列表页只拍到实际内容的一半）。**消除首屏与第二屏之间的缺口**：改为首步用保守步长起步、测出固定区域后再放宽。**修正懒加载列表的截断误报**：分段上限改按实际步长计算，并每段重读页面高度跟随增长。**拍不全/测不准不再静默**：`is_scroll_view_page` / `truncated` / `content_gaps` / `detection_confident` 此前要么被 `Math.max(0,...)` 夹掉、要么在 Python 侧 `_ok()` 中被丢弃（与 v0.9.15 那个「CDP 恒返回 0 条」同一类缺陷），现全部透传并在 message 中以 ⚠ 明示；`node_bridge` 失败分支同时保留 handler 给的 `hint`。真机验证（开发者工具 2.x）：帮助页 `fixed_header` 0 → 166、接缝导航栏重复消失，且旧版在接缝丢了一条内容；某列表页 3 段 3184px → 7 段 6815px；6 个页面用整条带匹配验证顶栏/底栏各只出现 1 次。**同时本项目源码已开源**（[#11](https://github.com/WaterTian/wechat-devtools-mcp/issues/11)），`src/` 与 214 项测试并入公开仓，新增 CONTRIBUTING.md；移除自 v0.9.5 起就未注册的 `wechat_cloud` 死代码 |
| **0.9.15** | **适配开发者工具 2.x(Electron) + 修复 CDP 采集长期失效**：开发者工具 2.x 改用 Electron（1.06.x Stable 仍是 NW.js，双轨兼容不替换）。macOS 启动路径按 `Resources/package.nw` 有无自动判定运行时、入口读 Info.plist 的 `CFBundleExecutable`，kill 模式改用 `.app` 包路径——旧模式匹配不到 Electron 进程，导致 macOS 上默认参数的 `wechat_ide(action='open')` 完全不可用；2.x 不再识别命令行 `--project`，改为先带 CDP 起进程再由 CLI 打开项目，并等 CDP 与 IDE 服务端口双双就绪才继续（否则 CLI 会另起一个不带 CDP 的实例，出现「项目开了但 CDP 连不上」的假成功）。**修复 `wechat_inspector(action='cdp')` 自 v0.9.0 起恒返回 0 条**——daemon 把结果放在 `data`，而 inspector 读的是并不存在的 `logs`，最常用的查错工具静默失灵了 8 个小版本。daemon 流上限由 asyncio 默认 64 KiB 提到 16 MiB（2.x 下 6 秒采集实测 634 KiB，超限会静默丢弃全部结果）。CDP 噪音过滤适配 2.x target 结构，剔除新增的 IDE 外壳页与因 `type=webview` 漏网的 `devtools://`（实测 734 条 → 206 条）。IDE 端口探测改读 IDE 落盘的 `.ide` 文件（硬编码候选端口在 2.x 下完全猜不中）；`status` 新增 `service_port_enabled`（`CLI_TIMEOUT` 的头号原因，现可自诊断）与 `ide_port`；`wechat_ide` / `wechat_build` 新增 `cdp_port` 参数（9222 常被 Chrome 占用） |
| **0.9.14** | **文件读取路径修复 + 参数失效修复**：`wechat_file` 的 `read_page`/`read_file` 改为与 `list_pages` 同口径（先按 `project.config.json` 的 `miniprogramRoot` 解析，再回退项目根）——此前云开发项目里 `list_pages` 返回的 `pages/xxx/index` 喂给 `read_page` 必然报「未找到页面文件」，SOP G 第一步即受影响；同名文件在两个根下都存在时新增 `also_found_at` 如实提示，`project.config.json` 固定取项目根那份权威副本；`read_page` 返回 `resolved_base`、`read_file` 返回 `resolved_path`。`wechat_inspector(action='cdp')` 补上 `cdp_port` 透传（此前该参数形同虚设，永远连 9222）。`subprocess.CREATE_NO_WINDOW` 全部改用 `getattr` 兜底，消除非 Windows 平台的 `AttributeError` 隐患 |
| **0.9.13** | **`--version` 早退 + 文档核对修复**：`wechat-devtools-mcp --version` / `-V` 零依赖打印安装版本后直接退出（uvx 复用已装环境不自拉最新，一行命令即可确认实际版本）；文档修复：navigate 参数表 5 列错位、`设置 -> 安全设置` 菜单名、`mcp_version` 示例去版本化；补记 `wechat_ide` `result_output` 与 `wechat_navigate` `timeout`（此前自 v0.6.0 起未进文档）；SKILL.md Step 1 新增 skill/MCP 版本一致性自检行 |
| **0.9.12** | **握手返回包版本 + 依赖上界**：mcp 2.x 下 `initialize` 的 `serverInfo.version` 由空串改为本包版本（1.x 下仍报 SDK 版本，SDK 无参数可覆盖）；依赖补上界 `mcp[cli]>=1.9,<3` 防范 mcp 未来大版本破坏；双版本导入统一收敛至 `_compat.py`（[#9](https://github.com/WaterTian/wechat-devtools-mcp/issues/9) [#10](https://github.com/WaterTian/wechat-devtools-mcp/issues/10)）|
| **0.9.11** | **兼容 mcp 2.0.0**：官方 MCP Python SDK 2.0（2026-07-28 发布）移除 `mcp.server.fastmcp`（改名 `MCPServer`）导致新装用户启动即崩，全部导入改为 1.x/2.x 双版本兼容；依赖明确为 `mcp[cli]>=1.9`（[#8](https://github.com/WaterTian/wechat-devtools-mcp/issues/8)）|
| **0.9.10** | **修复 page_path 静默失败**：screenshot.js 导航后验证页面路径是否匹配，缺少 `/index` 后缀或页面不存在时返回明确错误而非静默拍下旧页面；node_bridge.py 修复 daemon handler 错误信息丢失（[#5](https://github.com/WaterTian/wechat-devtools-mcp/issues/5)）|
| **0.9.9** | **修复截图导致小程序重启**：screenshot.js 对非 TabBar 页面的导航方式从 `reLaunch`（销毁全部页面栈）改为 `navigateTo`（非破坏性压栈），修复 macOS 环境下截图后模拟器重置问题（[#4](https://github.com/WaterTian/wechat-devtools-mcp/issues/4)）|
| **0.9.8** | **修复 automator 连接稳定性**：daemon.js `currentPage()` 健康检查改为轮询重试（新连接 5 次 × 3s+1.5s），不再因页面加载慢丢弃已建立的 WebSocket 连接；`_action_start` 改用 `_run_cli` 同步检测 CLI 返回码，CLI 失败立即感知（[#3](https://github.com/WaterTian/wechat-devtools-mcp/issues/3)）|
| **0.9.7** | **修复 daemon 孤儿进程残留**：daemon.js 增加父进程 watchdog，每 5 秒 `process.kill(ppid, 0)` 检测存活，父进程被杀后自动清理 WS 连接并退出（[#2](https://github.com/WaterTian/wechat-devtools-mcp/issues/2)）|
| **0.9.6** | **macOS 适配**：`cdp_enabled=true` 模式跨平台启动（NW.js 主程序 `wechatdevtools` + `package.nw` 入口 + `pkill` 清理）；默认 CLI 路径按平台返回；Node.js 检测补 Homebrew/nvm 候选路径；README 增加 macOS 路径示例 |
| **0.9.5** | **修复 compile 健康检查永久失败的潜伏 bug**（ui_debug.js 无 `page_stack` action，v0.9.0 以来 `automator_verified` 一直误报 false）；compile 对 `EACCES`/`EADDRINUSE`/`#initialize-error` 等致命 pattern 降级为 fail，杜绝「假成功发布旧 bundle」；preview 自动 resolve 相对路径 + mtime 新鲜度检测；`wechat_automator(action='start')` 升级为 TCP+WS 双重验证 + `retry_after_ms` 精确等待；compile 前检测 `miniprogram_npm` 过期发 warning；inspector 短 duration 捕获异常时发 warning；`wechat_cloud` 工具已禁用（改用 CloudBase MCP） |
| **0.9.4** | 修复 switchTab 跳转不生效（改用 `miniProgram.switchTab()` 替代 `callWxMethod`）；compile 后重连稳定性（去冗余进程 + 3s 延迟 + WS 健康检查）；README 5 项 agent 友好性改进 |

<details>
<summary>展开 v0.9.3 及更早版本</summary>

| 版本 | 说明 |
|------|------|
| 0.9.3 | status 新增 `mcp_version` 字段用于版本确认；启动时打印版本号到 stderr；README 增加 pip/uv 版本冲突排查指引 |
| 0.9.2 | **修复 compile 后 navigate 超时**：daemon 连接健康检查增加 3s 超时保护；compile 后自动 invalidate 旧缓存连接再重连；navigate currentPage 轮询每次调用增加 2s 独立超时；区分 HEALTH\_CHECK\_TIMEOUT 和 CONNECTION\_ERROR 错误码 |
| 0.9.1 | 修复 cdp\_enabled=true 时 AttributeError 崩溃；新增 WXML 运行时错误采集（compile 后 CDP 自动捕获 template not found 等警告） |
| 0.9.0 | **持久化 Node daemon 架构**：单 daemon 进程常驻，NDJSON 协议通信，WS 连接按端口复用；单个 daemon.bundle.js 替代 8 个独立 bundle；工具调用延迟从 500ms+ 降至 ~3ms；compile 后 daemon 自动重建连接零断连 |
| 0.8.0 | compile 后自动重连 automator；navigate 自动识别 TabBar 页面走 switchTab；screenshot 新增 full\_page/scroll\_top/page\_path 参数及视口截图模式；page\_data 新增 expected\_path 轮询防旧数据；长图拼接动态步长修复内容缺口；node\_bridge 统一连接断开重试 + 500ms 调用间隔；start 端口验证增至 20 次 |
| 0.7.0 | navigate 变量作用域修复（currentPageTimeout）；evaluate 支持声明语句（const/let/var fallback）；call_method 返回当前页面路径；automator start 端口轮询验证替代盲等；SKILL.md 新增效率原则、恢复分级、页面跳转方法、6 条故障条目 |
| 0.6.0 | navigate 支持 query 参数（reLaunch 超时 fallback）；CDP 启动噪音过滤（console.assert/\_\_route\_\_/ide:// 降噪 + WXML 错误保护）；compile 返回值三分类 + automator 失效提示；navigate currentPage 轮询重试；超时可配置 |
| 0.5.1 | `wechat_ide(action='open')` 新增 CDP 启动健康检查：自动采集 5 秒 CDP 日志检测启动阶段致命错误，有错误直接返回失败阻止后续操作 |
| 0.5.0 | Skill SOP 全面优化：新增 SOP I/J；增加 AppID 检查与 path 校验；CDP 噪音过滤；截图拼接模糊匹配修复 |
| 0.4.1 | 截图长页面拼接重写：固定区域检测、DPR 自适应、动态重叠计算 |
| 0.4.0 | CDP 日志增强、云函数部署自动验证、navigate 智能诊断、新增 SOP G/H |
| 0.3.0 | **重大重构**：44 个工具聚合为 8 个 API；CDP 日志 v2；新增 SKILL.md 知识库 |
| 0.2.6 | README 新增 OpenAI Codex 配置说明 |
| 0.2.5 | 新增 Kiro 编辑器配置说明 |
| 0.2.4 | 截图滚动拼接修复：`sharp` → `jimp` |
| 0.2.3 | 发布包优化：排除 `scripts/` 源码，仅保留 `dist/` 构建产物 |
| 0.2.2 | Node.js 脚本改为 bundle-only 模式 |
| 0.2.1 | 版本更新与文档完善 |
| 0.2.0 | navigate 改用 CDP 高清日志采集 |
| 0.1.9 | 修复 UTF-8 编码乱码 |
| 0.1.8 | 修复 Windows 中文路径 UnicodeDecodeError |
| 0.1.7 | 新增 core/full 工具集预设；新增 MCP_DOC.md |
| 0.1.6 | `wechat_open(cdp_enabled=true)` 自动 kill 已有进程 |
| 0.1.5 | 修复 Windows stdio 阻塞问题 |
| 0.1.4 | 添加 CDP 日志、截图、自动化等功能 |
| 0.1.3 | 初始版本 |
</details>
