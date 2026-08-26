"""Navigate 新增参数与诊断逻辑测试。"""
import pytest
from pydantic import ValidationError
from wechat_devtools_mcp.models.schemas import WechatNavigateInput


class TestNavigateSchema:
    """wechat_navigate 新增字段测试。"""

    def test_clear_logs_default_true(self):
        inp = WechatNavigateInput(page_path="pages/index/index")
        assert inp.clear_logs is True

    def test_clear_logs_can_be_false(self):
        inp = WechatNavigateInput(page_path="pages/index/index", clear_logs=False)
        assert inp.clear_logs is False

    def test_check_data_default_true(self):
        inp = WechatNavigateInput(page_path="pages/index/index")
        assert inp.check_data is True

    def test_check_data_can_be_false(self):
        inp = WechatNavigateInput(page_path="pages/index/index", check_data=False)
        assert inp.check_data is False


class TestPageDataDiagnostics:
    """page_data 空值检测逻辑测试。"""

    def _check_empty_ratio(self, page_data: dict) -> bool:
        """复制 navigate.py 中的诊断逻辑用于测试。"""
        fields = list(page_data.values())
        if len(fields) < 5:
            return False
        empty_count = sum(
            1 for v in fields
            if v is None or v == "" or v == [] or v == "undefined"
        )
        return empty_count / len(fields) > 0.7

    def test_mostly_empty_triggers_warning(self):
        data = {"a": None, "b": "", "c": [], "d": None, "e": "undefined", "f": None}
        assert self._check_empty_ratio(data) is True

    def test_normal_data_no_warning(self):
        data = {"a": "hello", "b": 42, "c": [1, 2], "d": True, "e": "world"}
        assert self._check_empty_ratio(data) is False

    def test_few_fields_no_warning(self):
        data = {"a": None, "b": None, "c": None}
        assert self._check_empty_ratio(data) is False

    def test_zero_and_false_not_empty(self):
        data = {"a": 0, "b": False, "c": 0, "d": False, "e": 0}
        assert self._check_empty_ratio(data) is False

    def test_empty_dict_not_empty(self):
        data = {"a": {}, "b": {}, "c": {}, "d": {}, "e": {}}
        assert self._check_empty_ratio(data) is False


class TestNavigateTimeout:
    """timeout 字段测试。"""

    def test_timeout_default_30(self):
        inp = WechatNavigateInput(page_path="pages/index/index")
        assert inp.timeout == 30

    def test_timeout_custom(self):
        inp = WechatNavigateInput(page_path="pages/index/index", timeout=60)
        assert inp.timeout == 60

    def test_timeout_min_10(self):
        with pytest.raises(ValidationError):
            WechatNavigateInput(page_path="pages/index/index", timeout=5)

    def test_timeout_max_120(self):
        with pytest.raises(ValidationError):
            WechatNavigateInput(page_path="pages/index/index", timeout=200)
