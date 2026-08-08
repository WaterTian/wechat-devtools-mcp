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
