"""
全局配置常量。从环境变量读取，提供合理默认值。
"""
import os
import sys


def _default_cli_path() -> str:
    if sys.platform == "darwin":
        return "/Applications/wechatwebdevtools.app/Contents/MacOS/cli"
    return r"D:\Tencent\微信web开发者工具\cli.bat"


# 微信开发者工具 CLI 路径
CLI_PATH: str = os.environ.get("WECHAT_DEVTOOLS_CLI", _default_cli_path())

# CLI 执行超时（秒）
CLI_TIMEOUT: int = int(os.environ.get("WECHAT_CLI_TIMEOUT", "30"))

# 默认小程序项目路径
DEFAULT_PROJECT_PATH: str | None = os.environ.get("WECHAT_PROJECT_PATH")

# MCP 根目录（用于定位脚本等资源）
MCP_ROOT: str = os.environ.get(
    "WECHAT_MCP_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Node.js 脚本所在目录
_SCRIPTS_DIR: str = os.environ.get(
    "WECHAT_SCRIPTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

# Node.js 可执行文件路径
_NODE_PATH: str = os.environ.get("NODE_PATH", "node")

# ── automator 就绪预算（2026-10-26 真机 2.02.2608060 实测）──
# `cli auto` 后 2.4s WS 即可连，但 `currentPage` 要 ~9s（冷启动 ~11s）才首次应答。
# 旧的「10s × 2 次」卡在边缘，负载稍高就把「还没准备好」报成「握手未完成」。
AUTOMATOR_READY_TIMEOUT: int = int(os.environ.get("WECHAT_AUTOMATOR_READY_TIMEOUT", "45"))

# 单次 daemon 探测（automation.js pageStack）的 Python 侧超时（秒）。
# 必须盖过 daemon 新连接健康检查上限（≈20s）：否则 Python 先超时放弃，daemon 还在重试，
# 连接被遗弃、下一次探测再起一个新连接。
WS_PROBE_TIMEOUT: int = 30

# compile 后自动重连 automator 的总预算（秒）。实测 compile 后多数情况下立即可用。
COMPILE_RECONNECT_TIMEOUT: int = 20
