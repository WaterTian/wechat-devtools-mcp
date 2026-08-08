# wechat-devstudio-mcp 源码镜像

本目录镜像 `wechat-devtools-mcp` PyPI 包中与本地修复相关的源码文件，供版本控制与回溯。

> 注意：此仓库（fork）原为「瘦 MCP + 胖 Skill」形态，仅跟踪文档与 Skill，Python 源码发布在 PyPI。
> 本 `src/` 目录用于持久化对已安装包的**本地补丁**，避免 `pip install -U` 覆盖后补丁丢失。

## 本补丁：修复 Windows 含空格/中文 CLI 路径的 `cmd /c` 引用

**文件**：`src/wechat_devtools_mcp/core/cli.py`

**问题**：`_run_cli` 在 Windows 上以 `cmd /c "<cli.bat>" ...` 方式调用 CLI。当 CLI 路径含空格
（如 `C:\Program Files (x86)\Tencent\微信开发者工具\cli.bat`）时，`cmd /c` 会剥离最外层引号，
导致路径被空格切分，报 `'C:\Program' 不是内部或外部命令`，进而表现为 `CLI_TIMEOUT` 或
`is_login` 恒为 `false`。

**修复**：改用双层引号包裹整个命令，`cmd /c ""<cli.bat>" ..."`，cmd 去掉最外层引号后路径引号
得以保留。同时只对含空格/非 ASCII 的参数加引号，避免 `cmd`、`/c` 等被误加引号。

**影响范围**：`is_login`、`login`、`automator start` 均经由 `_run_cli` 调用 CLI，一并修复。