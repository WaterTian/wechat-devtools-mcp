"""验证聚合工具的条件必填参数校验逻辑。"""
import pytest
from wechat_devtools_mcp.tools.automator import REQUIRED_PARAMS


class TestAutomatorRequiredParams:
    """automator 必填参数映射完整性测试。"""

    def test_tap_requires_selector(self):
        assert "selector" in REQUIRED_PARAMS["tap"]

    def test_input_requires_selector_and_value(self):
        assert "selector" in REQUIRED_PARAMS["input"]
        assert "value" in REQUIRED_PARAMS["input"]

    def test_mock_wx_requires_method_and_result(self):
        assert "method" in REQUIRED_PARAMS["mock_wx"]
        assert "result_json" in REQUIRED_PARAMS["mock_wx"]

    def test_evaluate_not_in_static_required_params(self):
        """evaluate 的必填是 expression / fn_source 二选一，不走静态表，
        由 wechat_automator 单独校验（见 tests/test_evaluate_fn_source.py）。"""
        assert "evaluate" not in REQUIRED_PARAMS
