"""compile 返回值三分类测试。"""
from wechat_devtools_mcp.tools.build import _classify_compile_line


class TestClassifyCompileLine:
    """stderr 行分类逻辑测试。"""

    def test_error_keyword(self):
        assert _classify_compile_line("[error] WXML file not found") == "error"

    def test_error_chinese(self):
        assert _classify_compile_line("编译错误：模块不存在") == "error"

    def test_fail_keyword(self):
        assert _classify_compile_line("fail to compile page") == "error"

    def test_warning_keyword(self):
        assert _classify_compile_line("[warning] deprecated API usage") == "warning"

    def test_warning_chinese(self):
        assert _classify_compile_line("警告：组件未使用") == "warning"

    def test_status_checkmark(self):
        assert _classify_compile_line("✓ IDE server has started") == "status"

    def test_status_sqrt(self):
        assert _classify_compile_line("√ compile success") == "status"

    def test_status_started(self):
        assert _classify_compile_line("IDE server has started on port 9222") == "status"

    def test_status_success(self):
        assert _classify_compile_line("build success") == "status"

    def test_status_done(self):
        assert _classify_compile_line("done in 3.2s") == "status"

    def test_unknown_defaults_to_status(self):
        """未命中任何关键词的行应归入 status 而非 error。"""
        assert _classify_compile_line("× compile_start") == "status"

    def test_skip_lines_return_none(self):
        assert _classify_compile_line("- initialize project") is None
        assert _classify_compile_line("✔ compiled successfully") is None
        assert _classify_compile_line("- preparing build") is None
        assert _classify_compile_line("- Fetching resources") is None
        assert _classify_compile_line("- Preview on device") is None
        assert _classify_compile_line("") is None
        assert _classify_compile_line("- compile wxml and wxss") is None
        assert _classify_compile_line("- pack files") is None


class TestRuntimeDeprecationNoise:
    """Node/Electron 弃用提示不是小程序告警（真机 2026-09-03，IDE 2.02.2608060 Stable）。"""

    def test_node_deprecation_line_skipped(self):
        line = "(node:35858) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead."
        assert _classify_compile_line(line) is None

    def test_trace_deprecation_hint_skipped(self):
        assert _classify_compile_line("(Use `Electron --trace-deprecation ...` to show where the warning was created)") is None
        assert _classify_compile_line("(Use `node --trace-deprecation ...` to show where the warning was created)") is None
        # Windows 上可执行名是中文主程序名（真机 2026-09-04，2.02.2608060）
        assert _classify_compile_line("(Use `微信开发者工具 --trace-deprecation ...` to show where the warning was created)") is None

    def test_use_prefix_without_trace_flag_not_skipped(self):
        """只有 --trace-deprecation 提示才跳过，别把以 (Use ` 开头的其它告警吞掉。"""
        assert _classify_compile_line("(Use `foo` warning: something deprecated)") == "warning"

    def test_real_deprecated_api_warning_still_counted(self):
        """项目代码里的 deprecated 告警不能被误杀。"""
        assert _classify_compile_line("[warning] wx.getSystemInfo is deprecated") == "warning"
