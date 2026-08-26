# 开放待办

> 记录已确认存在、但当时未处理的问题。每条都注明「为什么当时没做」，避免重复评估。
> 最后更新：2026-08-20（v0.9.15 发布后）

## P1 · `evaluate` 多语句静默截断

**现象**：`wechat_automator(action='evaluate', expression="a(); b(); c()")` **只执行第一条**，且不报任何错。

**根因**：`ui_debug.js` 先试 `new Function('return ' + code)`，拼出的 `return a(); b(); c()` 语法合法，
所以不会 fallback 到语句模式，而 `return` 之后全是死代码。

相关的第二个陷阱：走函数体模式时不写 `return` 就返回 `null`
（`const p=getCurrentPages(); p.length` → `null`）。

**当时为何没做**：可靠区分「表达式」与「语句序列」需要真正解析 JS，靠字符串启发式（数分号、
找顶层 `;`）会被字符串字面量、for 循环、箭头函数里的分号骗过去。v0.9.15 发版在即，
改 `evaluate` 的语义风险过高。

**现状**：已在 `SKILL.md`（注意事项 + 故障速查）与 `tool_reference.md`（加框警告）写明规避方式——
非单个表达式一律用 IIFE 包裹并显式 `return`。

**建议做法**：引入轻量 JS 解析（如 acorn，注意会增大 bundle）判断顶层语句数；或改为始终走
函数体模式、并在无 `return` 时自动补上最后一个表达式的返回。两种都要配回归测试覆盖
表达式 / 声明 / 多语句 / 字符串内含分号四类输入。

## P2 · Windows 侧 IDE 2.x 未验证

`_resolve_ide_executable_for_cdp` 的 Windows 分支仍是 `CLI_PATH.replace("cli.bat", "微信开发者工具.exe")`
+ kill 模式 `wechatdevtools.exe`。macOS 上 2.x 的这两处都已失效，Windows 大概率同样失效。

**当时为何没做**：当前开发环境是 macOS，官方文档与社区均未给出 2.x 的 Windows 目录结构，无从验证。

**建议做法**：在 Windows 机装 2.x 开发版后，按 macOS 的排查路径确认主程序名与进程命令行，
并把硬编码改为防御式探测（候选名依次探测 + 从 CLI 路径推导）。

## P3 · Linux 适配

`_resolve_ide_executable_for_cdp` 对 linux 抛 `NotImplementedError`。第三方 Linux 移植版是否保留
同样的 Electron 结构未知。有真机时按 `docs/macos-internals.md` 的结构补。

## P4 · IDE 2.x 项目窗口自动关闭（现象记录，未查根因）

2026-08-20 测试期间遇到 4 次：IDE 主进程仍在，但项目窗口自行关闭，表现为 automator 9420 断连、
CDP 只剩 IDE 外壳 target。用 `cli open --project` + `cli auto` 可恢复。

尚未确认是 2.x 预览版自身的稳定性问题，还是被我们的操作触发（例如 CLI 会话结束、
或多次 `cli auto` 之后）。属预览版行为，暂作观察记录。

## P5 · 杂项清理

- `.gitignore` 里的 `.mcpregistry_registry_token`：全流程无任何命令引用，属旧版 publisher 遗留
