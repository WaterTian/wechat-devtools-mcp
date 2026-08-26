"""验证 7 个聚合输入 Schema 的 action Literal 枚举和字段定义。"""
import pytest
from pydantic import ValidationError
from wechat_devtools_mcp.models.schemas import (
    WechatIdeInput, WechatBuildInput, WechatAutomatorInput,
    WechatInspectorInput, WechatScreenshotInput, WechatNavigateInput,
    WechatFileInput,
)


class TestIdeSchema:
    """wechat_ide Schema 测试。"""

    @pytest.mark.parametrize("action", ["open", "login", "is_login", "close", "quit", "status"])
    def test_valid_actions(self, action: str):
        """验证所有合法 action 可以通过校验。"""
        inp = WechatIdeInput(action=action)
        assert inp.action == action

    def test_invalid_action_rejected(self):
        """非法 action 应被 Pydantic 拒绝。"""
        with pytest.raises(ValidationError):
            WechatIdeInput(action="invalid_action")


class TestBuildSchema:
    """wechat_build Schema 测试。"""

    @pytest.mark.parametrize("action", ["compile", "preview", "upload", "build_npm", "cache_clean"])
    def test_valid_actions(self, action: str):
        inp = WechatBuildInput(action=action)
        assert inp.action == action


class TestAutomatorSchema:
    """wechat_automator Schema 测试。"""

    VALID_ACTIONS = [
        "start", "tap", "input", "element_info",
        "set_data", "call_method", "call_wx", "mock_wx",
        "evaluate", "page_stack", "page_data", "system_info", "storage",
    ]

    @pytest.mark.parametrize("action", VALID_ACTIONS)
    def test_valid_actions(self, action: str):
        inp = WechatAutomatorInput(action=action)
        assert inp.action == action

    def test_auto_port_range_validation(self):
        """端口超出范围应被拒绝。"""
        with pytest.raises(ValidationError):
            WechatAutomatorInput(action="start", auto_port=99999)
        with pytest.raises(ValidationError):
            WechatAutomatorInput(action="start", auto_port=0)


class TestInspectorSchema:
    """wechat_inspector Schema 测试。"""

    @pytest.mark.parametrize("action", ["console", "cdp"])
    def test_valid_actions(self, action: str):
        inp = WechatInspectorInput(action=action)
        assert inp.action == action

    def test_duration_range(self):
        """duration 范围应为 1-120。"""
        with pytest.raises(ValidationError):
            WechatInspectorInput(action="cdp", duration=0)
        with pytest.raises(ValidationError):
            WechatInspectorInput(action="cdp", duration=121)


class TestScreenshotSchema:
    """wechat_screenshot Schema 测试。"""

    def test_output_path_optional(self):
        """output_path 为可选字段（v0.4.1 起改为可选，留空自动保存到 screenshots/）。"""
        inp = WechatScreenshotInput()
        assert inp.output_path is None
    
    def test_valid_input(self):
        inp = WechatScreenshotInput(output_path="C:\\tmp\\shot.png")
        assert inp.output_path == "C:\\tmp\\shot.png"


class TestNavigateSchema:
    """wechat_navigate Schema 测试。"""

    def test_page_path_required(self):
        with pytest.raises(ValidationError):
            WechatNavigateInput()


class TestFileSchema:
    """wechat_file Schema 测试。"""

    @pytest.mark.parametrize("action", ["project_info", "list_pages", "read_page", "read_file"])
    def test_valid_actions(self, action: str):
        inp = WechatFileInput(action=action)
        assert inp.action == action
