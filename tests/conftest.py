"""公共测试 fixtures。"""
import os
import sys
import pytest

# 添加 src 到导入路径（须在 import 包之前，editable 安装不含新增模块）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from wechat_devtools_mcp._compat import FastMCP
from wechat_devtools_mcp.tools import register_all_tools


@pytest.fixture(autouse=True)
def _no_real_cdp_port_probe(monkeypatch):
    """open / status / inspector / compile / navigate 都会先探测 CDP 端口上是谁。
    单测默认当作无人监听（kind=none），避免去碰真实端口——开发机的 9222 常年是 Chrome，
    真探会把用例变成随机失败。需要别的占用者的用例自行覆盖 ide._port_listening / _http_get_json
    或各模块的 _inspect_cdp_port。"""
    from wechat_devtools_mcp.tools import ide
    monkeypatch.setattr(ide, "_port_listening", lambda port: False)


@pytest.fixture(autouse=True)
def _isolate_cdp_session_port():
    """会话内粘性的 CDP 端口是模块级状态：open 成功会记住端口，必须逐测试清零，
    否则 test_ide_open_speed 里 open(cdp_port=9223) 会漏到后面断言默认 9222 的用例。"""
    from wechat_devtools_mcp.core import cdp_port
    cdp_port.forget_cdp_port()
    yield
    cdp_port.forget_cdp_port()


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
