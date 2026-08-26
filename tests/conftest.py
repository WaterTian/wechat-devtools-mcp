"""公共测试 fixtures。"""
import os
import sys
import pytest

# 添加 src 到导入路径（须在 import 包之前，editable 安装不含新增模块）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from wechat_devtools_mcp._compat import FastMCP
from wechat_devtools_mcp.tools import register_all_tools


@pytest.fixture
def mcp_instance():
    """创建已注册全部工具的 FastMCP 实例。"""
    mcp = FastMCP("test")
    register_all_tools(mcp)
    return mcp


@pytest.fixture
def set_env_vars(tmp_path):
    """设置测试用环境变量，测试结束后恢复。"""
    original = {}
    test_vars = {
        "WECHAT_DEVTOOLS_CLI": r"C:\fake\cli.bat",
        "WECHAT_PROJECT_PATH": str(tmp_path),
    }
    for key, value in test_vars.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value
    yield tmp_path
    for key, orig_val in original.items():
        if orig_val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = orig_val
