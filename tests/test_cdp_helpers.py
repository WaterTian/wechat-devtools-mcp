"""CDP 日志分类与格式化测试。"""
import pytest
from wechat_devtools_mcp.utils.cdp_helpers import _classify_cdp_log, _format_cdp_logs_v2


class TestClassifyCdpLog:
    """单条 CDP 日志分类测试。"""

    def test_runtime_console_error(self):
        log = {
            "type": "RUNTIME_CONSOLE",
            "url": "appservice/pages/index/index.js",
            "content": {"args": [{"value": "test error"}], "type": "error"},
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "error"
        assert "test error" in message

    def test_console_message_added(self):
        log = {
            "type": "CONSOLE",
            "url": "",
            "content": {"text": "Component not found", "level": "error", "url": "index.wxml"},
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "error"
        assert source == "index.wxml"

    def test_exception_type(self):
        log = {
            "type": "EXCEPTION",
            "url": "",
            "content": {"exception": {"description": "TypeError: undefined"}},
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "error"


class TestFormatCdpLogsV2:
    """CDP 日志结构化格式化测试。"""

    @pytest.fixture
    def sample_logs(self):
        return [
            {"type": "RUNTIME_CONSOLE", "url": "", "content": {"args": [{"value": "error msg"}], "type": "error"}},
            {"type": "RUNTIME_CONSOLE", "url": "", "content": {"args": [{"value": "warn msg"}], "type": "warning"}},
            {"type": "RUNTIME_CONSOLE", "url": "", "content": {"args": [{"value": "info msg"}], "type": "log"}},
        ]

    def test_summary_structure(self, sample_logs):
        result = _format_cdp_logs_v2(sample_logs, "full", 50)
        assert "summary" in result
        assert result["summary"]["total"] == 3

    def test_concise_mode_filters_info(self, sample_logs):
        """concise 模式应排除 info 级别日志。"""
        result = _format_cdp_logs_v2(sample_logs, "concise", 50)
        for log in result["logs"]:
            assert log["level"] in ("error", "warning")

    def test_truncation(self, sample_logs):
        """超过 max_logs 时应截断。"""
        result = _format_cdp_logs_v2(sample_logs, "full", max_logs=1)
        assert result["summary"]["truncated"] is True
        assert len(result["logs"]) <= 1


class TestObjectObjectHint:
    """[object Object] 残留检测测试。"""

    def test_object_object_in_args_gets_hint(self):
        """含 [object Object] 的日志应在 message 中包含 hint。"""
        log = {
            "type": "RUNTIME_CONSOLE",
            "url": "",
            "content": {"args": ["加载失败", "[object Object]"], "type": "error"},
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "error"
        assert "[object Object]" in message

    def test_format_v2_adds_hint_for_object_object(self):
        """format_v2 应在含 [object Object] 的日志中附加 hint。"""
        logs = [
            {"type": "RUNTIME_CONSOLE", "url": "", "content": {"args": ["失败", "[object Object]"], "type": "error"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50)
        assert len(result["logs"]) == 1
        assert "hint" in result["logs"][0]
        assert "evaluate" in result["logs"][0]["hint"]


class TestAssertType:
    """console.assert 应降级为 warning 而非 error。"""

    def test_assert_classified_as_warning(self):
        log = {
            "type": "ASSERT",
            "url": "devtools://devtools/bundled/inspector.js",
            "content": {"args": [{"value": "assertion failed"}], "type": "assert"},
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "warning"
        assert "assertion failed" in message


class TestLogEntryType:
    """Log.entryAdded 事件应正确分类。"""

    def test_log_entry_error(self):
        log = {
            "type": "LOG_ENTRY",
            "url": "",
            "content": {
                "level": "error",
                "text": "./pages/index/index.wxml(line 5): Bad attr 'wx:forr'",
                "url": "pages/index/index.wxml",
            },
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "error"
        assert "Bad attr" in message

    def test_log_entry_warning(self):
        log = {
            "type": "LOG_ENTRY",
            "url": "",
            "content": {
                "level": "warning",
                "text": "some deprecation warning",
            },
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "warning"

    def test_log_entry_info(self):
        log = {
            "type": "LOG_ENTRY",
            "url": "",
            "content": {
                "level": "info",
                "text": "page loaded",
            },
        }
        level, message, source = _classify_cdp_log(log)
        assert level == "info"


class TestStartupNoiseFiltering:
    """启动噪音在 filter_startup_noise=True 时应被过滤。"""

    def test_route_noise_filtered(self):
        logs = [
            {"type": "EXCEPTION", "url": "", "content": {"exception": {"description": "Cannot read property '__route__' of undefined"}}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 0

    def test_ide_extensions_noise_filtered(self):
        logs = [
            {"type": "RUNTIME_CONSOLE", "url": "ide:///extensions/some-ext.js", "content": {"args": [{"value": "ext error"}], "type": "error"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 0

    def test_devtools_url_noise_filtered(self):
        logs = [
            {"type": "RUNTIME_CONSOLE", "url": "devtools://devtools/bundled/foo.js", "content": {"args": [{"value": "internal"}], "type": "error"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 0

    def test_inspectee_noise_filtered(self):
        """IDE 2.x 扩展注入的 inspectee 错误（真机 2026-09-04：外层 url 是
        appservice mainframe，ide:///extensions/ 只在 CONSOLE 类型的 content.url 里，
        RUNTIME_CONSOLE 的原始日志不含该字符串，只能靠 message 特征过滤）。"""
        logs = [
            {"type": "RUNTIME_CONSOLE",
             "url": "http://127.0.0.1:32965/appservice/s0/_sessionId/x/mainframe?load",
             "content": {"args": [
                 {"value": "inspectee MPPage.getCurrent error:"},
                 {"value": "TypeError: Cannot destructure property 'rawPath' of 't.getPageMetaByWebviewId(...)' as it is null."},
             ], "type": "error"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 0

    def test_access_token_expired_noise_filtered(self):
        """登录过期（access_token expired）是环境状态而非启动致命错误
        （真机 2026-09-04），不应让 open 的启动健康检查误报页面异常。"""
        logs = [
            {"type": "RUNTIME_CONSOLE",
             "url": "http://127.0.0.1:32965/appservice/s0/_sessionId/x/mainframe?load",
             "content": {"args": [{"value": "loadUserData error: <Error: cloud.callFunction:fail Error: access_token expired (trace: ...)"}], "type": "error"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 0

    def test_wxml_error_preserved_despite_noise_filter(self):
        """WXML 编译错误即使在噪音过滤模式下也必须保留。"""
        logs = [
            {"type": "LOG_ENTRY", "url": "", "content": {"level": "error", "text": "./pages/index/index.wxml(line 3): Bad attr", "url": "pages/index/index.wxml"}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50, filter_startup_noise=True)
        assert result["summary"]["errors"] == 1

    def test_noise_not_filtered_by_default(self):
        """默认模式不应过滤启动噪音。"""
        logs = [
            {"type": "EXCEPTION", "url": "", "content": {"exception": {"description": "Cannot read property '__route__' of undefined"}}},
        ]
        result = _format_cdp_logs_v2(logs, "full", 50)
        assert result["summary"]["errors"] == 1
