"""
7 个聚合工具的 Pydantic 输入 Schema。

使用 Literal 限制 action 字段，条件必填参数在工具内部校验。
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class WechatIdeInput(BaseModel):
    """IDE 生命周期管理聚合输入。"""
    action: Literal["open", "login", "is_login", "close", "quit", "status"] = Field(
        ..., description="操作类型。"
    )
    project_path: Optional[str] = Field(default=None, description="小程序项目路径。")
    appid: Optional[str] = Field(default=None, description="小程序 AppID。")
    port: Optional[int] = Field(default=None, description="IDE HTTP 服务端口号。", ge=1, le=65535)
    lang: Optional[str] = Field(default=None, description="界面语言：'en' 或 'zh'。")
    cdp_enabled: bool = Field(default=True, description="是否开启 CDP 调试端口。")
    cdp_port: int = Field(
        default=9222, ge=1, le=65535,
        description="CDP 调试端口，默认 9222。被 Chrome 等占用时可换端口（需与 inspector/navigate 保持一致）。",
    )
    qr_format: Optional[str] = Field(default="terminal", description="二维码格式：'terminal'、'image'、'base64'。")
    qr_output: Optional[str] = Field(default=None, description="二维码输出文件路径。")
    result_output: Optional[str] = Field(default=None, description="登录结果输出文件路径。")


class WechatBuildInput(BaseModel):
    """构建与发布聚合输入。"""
    action: Literal["compile", "preview", "upload", "build_npm", "cache_clean"] = Field(
        ..., description="操作类型。"
    )
    project_path: Optional[str] = Field(default=None, description="小程序项目路径。")
    version: Optional[str] = Field(default=None, description="版本号，upload 时必填。")
    desc: Optional[str] = Field(default=None, description="版本描述，upload 时使用。")
    qr_format: Optional[str] = Field(default="base64", description="二维码格式。")
    qr_output: Optional[str] = Field(default=None, description="二维码输出文件路径。")
    info_output: Optional[str] = Field(default=None, description="编译信息输出 JSON 文件路径。")
    compile_condition: Optional[str] = Field(default=None, description="自定义编译条件（JSON 字符串）。")
    compile_type: Optional[str] = Field(default=None, description="编译类型：'miniprogram' 或 'plugin'。")
    clean_type: str = Field(default="compile", description="缓存类型：'storage'、'file'、'compile'、'auth'、'network'、'session'、'all'。")
    cdp_port: int = Field(
        default=9222, ge=1, le=65535,
        description="CDP 调试端口，compile 采集 WXML 运行时错误时使用。需与 wechat_ide(open) 的 cdp_port 一致。",
    )
    port: Optional[int] = Field(default=None, description="IDE HTTP 服务端口号。", ge=1, le=65535)
    lang: Optional[str] = Field(default=None, description="界面语言。")


class WechatAutomatorInput(BaseModel):
    """自动化交互聚合输入。"""
    action: Literal[
        "start", "tap", "input", "element_info",
        "set_data", "call_method", "call_wx", "mock_wx",
        "evaluate", "page_stack", "page_data", "system_info", "storage"
    ] = Field(..., description="操作类型。")

    auto_port: int = Field(default=9420, description="自动化端口。", ge=1, le=65535)
    project_path: Optional[str] = Field(default=None, description="小程序项目路径，start 时使用。")

    # 条件参数
    selector: Optional[str] = Field(default=None, description="CSS 选择器，tap/input/element_info 时必填。")
    value: Optional[str] = Field(default=None, description="输入值，input 时必填。")
    style_prop: Optional[str] = Field(default=None, description="CSS 属性名，element_info 时可选。")
    data_json: Optional[str] = Field(default=None, description="JSON 数据，set_data 时必填。")
    method: Optional[str] = Field(default=None, description="方法名，call_method/call_wx/mock_wx 时必填。")
    args_json: Optional[str] = Field(default=None, description="方法参数 JSON 数组，call_method/call_wx 时可选。")
    expression: Optional[str] = Field(default=None, description="JS 表达式，evaluate 时必填。")
    result_json: Optional[str] = Field(default=None, description="Mock 返回值 JSON，mock_wx 时必填。")
    key: Optional[str] = Field(default=None, description="Storage key，storage 时可选。")
    auto_account: Optional[str] = Field(default=None, description="指定 openid，start 时可选。")
    expected_path: Optional[str] = Field(default=None, description="期望的页面路径，page_data 时可选。传入后会轮询验证当前页面是否匹配。")


class WechatInspectorInput(BaseModel):
    """日志采集聚合输入。"""
    action: Literal["console", "cdp"] = Field(..., description="采集方式。")
    duration: int = Field(
        default=10, ge=1, le=120,
        description=(
            "采集持续时间（秒）。两种 action 对历史消息的行为不同："
            "cdp —— CDP 的 Console.enable 会回放缓冲区，**采集开始之前的消息也能拿到**"
            "（实测 12 秒前打的错误仍可捕获），与 IDE 调试器面板看到的一致；"
            "console —— 基于 automator 事件监听，只收连接建立后的事件，历史消息追不回，"
            "排查 exception 建议 ≥8s 以覆盖页面加载后续事件窗口。"
        ),
    )

    # cdp 参数
    detail_level: Literal["concise", "full"] = Field(
        default="concise",
        description="concise：仅返回 summary + errors/warnings；full：返回全量日志。",
    )
    max_logs: int = Field(default=50, ge=1, le=500, description="最大返回日志条数，超出时截断并标注 truncated=true。")
    cdp_port: int = Field(default=9222, description="CDP 调试端口。", ge=1, le=65535)

    # console 参数
    auto_port: int = Field(default=9420, description="自动化端口。", ge=1, le=65535)
    log_type: Optional[Literal["all", "console", "exception"]] = Field(
        default="all", description="监听类型，console action 时使用。"
    )
    tap_selector: Optional[str] = Field(default=None, description="采集期间自动点击的 CSS 选择器。")
    tap_delay: int = Field(default=500, ge=0, description="点击延迟（毫秒）。")


class WechatScreenshotInput(BaseModel):
    """截图工具输入。"""
    output_path: Optional[str] = Field(default=None, description="截图保存路径。留空则自动保存到项目目录下 screenshots/ 文件夹。")
    auto_port: int = Field(default=9420, description="自动化端口。", ge=1, le=65535)
    overlap: int = Field(default=50, description="分段重叠像素数（默认 50）。")
    full_page: bool = Field(default=True, description="是否截取长图（默认 True）。设为 False 只截当前视口。")
    scroll_top: Optional[int] = Field(default=None, description="截图前滚动到的位置（逻辑像素）。配合 full_page=False 截取特定位置。", ge=0)
    page_path: Optional[str] = Field(default=None, description="确保截图前在指定页面上。若当前页面不匹配则自动跳转。")


class WechatNavigateInput(BaseModel):
    """页面跳转并采集 CDP 日志工具输入。"""
    page_path: str = Field(..., description="要跳转的页面路径，支持 query 参数，例如 'pages/detail/detail?id=123'。")
    clear_logs: bool = Field(default=True, description="是否过滤跳转前的 CDP 历史日志（基于时间戳），默认 True。")
    check_data: bool = Field(default=True, description="跳转后是否检查 page_data 并在数据大部分为空时发出警告，默认 True。")
    wait_ms: int = Field(default=2000, ge=100, le=30000, description="跳转后等待时间（毫秒）。")
    timeout: int = Field(default=30, ge=10, le=120, description="总超时时间（秒），复杂页面可适当增大。")
    auto_port: int = Field(default=9420, description="自动化端口。", ge=1, le=65535)
    cdp_port: int = Field(default=9222, description="CDP 调试端口。", ge=1, le=65535)
    detail_level: Literal["concise", "full"] = Field(default="concise", description="CDP 日志详略模式。")
    max_logs: int = Field(default=50, ge=1, le=500, description="最大 CDP 日志条数。")
    project_path: Optional[str] = Field(default=None, description="小程序项目路径（仅用于提示）。")


class WechatFileInput(BaseModel):
    """文件读取聚合输入。"""
    action: Literal["project_info", "list_pages", "read_page", "read_file"] = Field(
        ..., description="操作类型。"
    )
    project_path: Optional[str] = Field(default=None, description="小程序项目路径。")
    page_path: Optional[str] = Field(default=None, description="页面路径，read_page 时必填，例如 'pages/index/index'。")
    file_path: Optional[str] = Field(default=None, description="相对文件路径，read_file 时必填，例如 'app.json'。")
