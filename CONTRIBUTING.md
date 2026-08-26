# 贡献指南

## 架构概览

本项目采用「**瘦 MCP + 胖 Skill**」架构：Python MCP Server 只提供 7 个聚合 API，
真正的操作流程（SOP）沉淀在 `.agents/skills/` 的 Skill 知识库里。

```
编辑器 AI
   │  MCP stdio
Python MCP Server (src/wechat_devtools_mcp/)
   ├── tools/*.py       7 个聚合工具的 handler（按 action 分发）
   ├── core/cli.py      ──► 微信开发者工具 CLI（临时文件捕获输出，避开 stdio 冲突）
   └── core/node_bridge ──► NDJSON ──► 常驻 Node daemon (dist/daemon.bundle.js)
                                          ├── miniprogram-automator WebSocket (9420)
                                          └── CDP (9222)
```

| 目录 | 职责 |
|------|------|
| `src/wechat_devtools_mcp/tools/` | 7 个聚合工具的 Python handler |
| `src/wechat_devtools_mcp/core/` | CLI 调用、Node daemon 桥接、配置、IDE 状态读取 |
| `src/wechat_devtools_mcp/models/` | Pydantic 输入 schema |
| `src/wechat_devtools_mcp/scripts/` | Node.js 源码；`dist/daemon.bundle.js` 是 ncc 构建产物（已入库） |
| `tests/` | pytest 单元测试（mock `_run_node_script`，不依赖真实 IDE） |
| `.agents/skills/` | Skill 知识库（SOP 流程 + 参数速查） |
| `docs/` | 实现说明与开放待办 |

## 开发环境

```bash
pip install -e .                    # 开发安装
python -m pytest tests/ -q          # 全量测试（205 项，无需启动 IDE）
```

测试通过 `tests/conftest.py` 把 `src/` 插入 `sys.path`，因此**不装包也能直接跑**。

另有两个不归 pytest 管的独立脚本，改动截图逻辑时需手动执行：

```bash
node tests/test_screenshot_detect.js   # 长图拼接的固定区域像素检测
node tests/test_screenshot_scroll.js   # 滚动等待逻辑（长图截断的根因）
```

两者都直接 `require` 线上的 `screenshot.js`，不复制实现，因此能真正守护源码。

## 修改 JS 后必须重建 bundle

`scripts/*.js` 的改动不会自动生效——运行时加载的是 `scripts/dist/daemon.bundle.js`。
改完必须重建并**与源码一起提交**：

```bash
cd src/wechat_devtools_mcp/scripts
npm install
npx ncc build daemon.js -o dist/daemon_tmp \
  && mv dist/daemon_tmp/index.js dist/daemon.bundle.js \
  && rm -rf dist/daemon_tmp
```

daemon.js 通过 `require` 引入其余各 handler，因此**只需构建 daemon.js 这一个入口**。

## 提 PR 前的检查清单

1. `python -m py_compile src/wechat_devtools_mcp/server.py` 语法检查通过
2. `python -m pytest tests/ -q` 全绿
3. 改了 JS → bundle 已重建并一并提交
4. 新功能带测试（先写 failing test，再实现）

## 版本号同步（发版时，共 9 处）

改版本号时以下 9 处必须一致，漏改会导致客户端显示的版本与实际不符：

| # | 文件 | 位置 |
|---|------|------|
| 1 | `pyproject.toml` | `version = ` |
| 2 | `src/wechat_devtools_mcp/__init__.py` | `__version__` |
| 3-4 | `server.json` | 顶层 `version` + `packages[0].version` |
| 5 | `README.md` | 标题 |
| 6 | `README_EN.md` | 标题 |
| 7 | `MCP_DOC.md` | 标题 |
| 8 | `.agents/skills/wechat-devtools/SKILL.md` | frontmatter `version:` 与正文标题 |
| 9 | `.agents/skills/wechat-devtools/references/tool_reference.md` | 标题 |

## 跨平台注意事项

- Windows-only 的 `subprocess` 属性统一用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)` 兜底，
  不要直接引用，否则非 Windows 平台会 `AttributeError`
- 开发者工具 1.x(NW.js) 与 2.x(Electron) 的启动路径不同，必须双轨兼容，
  细节见 [`docs/macos-internals.md`](docs/macos-internals.md)
- 代码里对 IDE 内部文件（`.ide` / `.cli` / `.ide-status`）的读取**必须能优雅回退**——
  这些是官方未承诺的实现细节

## 想找事情做？

[`docs/TODO.md`](docs/TODO.md) 记录了已确认存在、但尚未处理的问题，每条都注明了「当时为何没做」。
其中 **P2（Windows 侧 IDE 2.x 未验证）** 和 **P3（Linux 适配）** 缺的是真机环境而非思路，
如果你手上有对应平台的机器，这两条最容易推进。

## 提交信息风格

`fix(scope):` / `feat(scope):` / `docs(scope):`，scope 用工具名，如 `navigate`、`evaluate`、`automator`。
