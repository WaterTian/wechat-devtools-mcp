"""serverInfo.version 支持测试（issue #10）。

mcp 2.x 的 MCPServer 有 version 参数，握手应报本包版本；
mcp 1.x 的 FastMCP 无此参数，_server_kwargs 应跳过传参避免 TypeError。
本套测试在两种 SDK 版本下都应通过（kwargs 与 SDK 能力一致即可）。

另含 --version/-V 命令行早退测试：零依赖查询本包版本，不起 stdio server，
且优先于环境变量校验（未配置环境变量的机器上也能查）。
"""
import inspect
import io
import sys
from unittest.mock import patch

from wechat_devtools_mcp import __version__, server
from wechat_devtools_mcp._compat import FastMCP


class TestServerVersion:
    """_server_kwargs 与 SDK 能力匹配性测试。"""

    def test_kwargs_match_sdk_capability(self):
        """有 version 参数时传本包版本，无则不传。"""
        has_version = "version" in inspect.signature(FastMCP.__init__).parameters
        kwargs = server._server_kwargs()
        assert ("version" in kwargs) == has_version
        if has_version:
            assert kwargs["version"] == __version__

    def test_module_imports_without_typeerror(self):
        """server.py 模块级构造在当前 SDK 下不抛异常。"""
        assert server.mcp is not None

    def test_compat_provides_fastmcp(self):
        """_compat 模块在 1.x/2.x 下都应导出 FastMCP。"""
        assert hasattr(FastMCP, "tool")


class TestVersionEarlyExit:
    """--version / -V 早退分支测试。"""

    def _run_main_with_argv(self, argv: list[str], capsys) -> int:
        """以指定 argv 运行 main()，返回退出码（0=正常返回，1=exit(1)）。

        main() 会用 TextIOWrapper 重新包装 stdio（Windows UTF-8），
        测试后必须还原，否则破坏 pytest 的捕获流导致 teardown 崩溃。
        """
        saved_out, saved_err = sys.stdout, sys.stderr
        try:
            with patch.object(sys, "argv", ["wechat-devtools-mcp"] + argv):
                with patch.object(server.mcp, "run") as mock_run:
                    try:
                        server.main()
                    except SystemExit as e:
                        return e.code if isinstance(e.code, int) else 1
        finally:
            # detach 防止 main() 创建的 wrapper 在 GC 时关闭底层
            # pytest 捕获流 buffer（TextIOWrapper.__del__ 会 close buffer）
            for s in (sys.stdout, sys.stderr):
                if isinstance(s, io.TextIOWrapper) and s is not saved_out and s is not saved_err:
                    try:
                        s.detach()
                    except (ValueError, OSError):
                        pass
            sys.stdout, sys.stderr = saved_out, saved_err
        return 0 if not mock_run.called else -1  # -1 表示 mcp.run 被意外调用

    def test_version_flag_prints_version(self, capsys, monkeypatch):
        """--version 打印本包版本并直接返回，不起 server。"""
        monkeypatch.delenv("WECHAT_DEVTOOLS_CLI", raising=False)
        monkeypatch.delenv("WECHAT_PROJECT_PATH", raising=False)
        code = self._run_main_with_argv(["--version"], capsys)
        assert code == 0
        assert __version__ in capsys.readouterr().out

    def test_short_version_flag(self, capsys, monkeypatch):
        """-V 等价于 --version。"""
        monkeypatch.delenv("WECHAT_DEVTOOLS_CLI", raising=False)
        monkeypatch.delenv("WECHAT_PROJECT_PATH", raising=False)
        code = self._run_main_with_argv(["-V"], capsys)
        assert code == 0
        assert __version__ in capsys.readouterr().out

    def test_no_flag_still_validates_env(self, monkeypatch):
        """不带 --version 时维持原行为：缺环境变量则 exit 1。

        只断言退出码：main() 会重新包装 sys.stderr（UTF-8），
        绕过 capsys 捕获，stderr 文本内容无法在测试中断言。
        """
        monkeypatch.delenv("WECHAT_DEVTOOLS_CLI", raising=False)
        monkeypatch.delenv("WECHAT_PROJECT_PATH", raising=False)
        code = self._run_main_with_argv([], capsys=None)
        assert code == 1
