"""读取微信开发者工具写在用户目录下的运行时状态文件。

IDE 每次启动都会把自己的端口和开关状态落盘，比在候选端口列表里瞎猜可靠得多。
实测（macOS，IDE 2.02.2607271）目录结构：

    ~/Library/Application Support/微信开发者工具/<32位hash>/Default/
        .ide         → "11071"   IDE 服务端口（CLI 就是靠它找到 IDE）
        .cli         → "3799"    CLI 端口
        .ide-status  → "On"      服务端口开关状态

多个 <hash> 目录会共存（不同版本/渠道各一份），取最近写入的那个。
读不到时一律返回 None，由调用方回退到原有探测方式——这些是内部实现细节，
官方未作承诺，不能当作硬依赖。
"""
import os
import sys
from typing import Optional

# 状态文件所在的子目录
_PROFILE_SUBDIR = "Default"

# IDE 用户数据目录名（各平台一致）
_APP_DIR_NAME = "微信开发者工具"


def _user_data_dirs() -> list[str]:
    """返回可能的 IDE 用户数据根目录，按可能性排序。"""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return [os.path.join(home, "Library", "Application Support", _APP_DIR_NAME)]
    if sys.platform == "win32":
        candidates = []
        for env in ("APPDATA", "LOCALAPPDATA", "USERPROFILE"):
            base = os.environ.get(env)
            if base:
                candidates.append(os.path.join(base, _APP_DIR_NAME))
        return candidates
    return [os.path.join(home, ".config", _APP_DIR_NAME)]


def _state_files(name: str) -> list[str]:
    """收集所有 profile 下同名状态文件，按修改时间从新到旧排序。"""
    found: list[tuple[float, str]] = []
    for base in _user_data_dirs():
        if not os.path.isdir(base):
            continue
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for entry in entries:
            path = os.path.join(base, entry, _PROFILE_SUBDIR, name)
            try:
                if os.path.isfile(path):
                    found.append((os.path.getmtime(path), path))
            except OSError:
                continue
    found.sort(reverse=True)
    return [p for _, p in found]


def _read_first(name: str) -> Optional[str]:
    """读取最近写入的那份状态文件内容。"""
    for path in _state_files(name):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            continue
    return None


def read_ide_port() -> Optional[int]:
    """IDE 服务端口，读不到返回 None。"""
    value = _read_first(".ide")
    try:
        return int(value) if value else None
    except ValueError:
        return None


def read_cli_port() -> Optional[int]:
    """CLI 端口，读不到返回 None。"""
    value = _read_first(".cli")
    try:
        return int(value) if value else None
    except ValueError:
        return None


def read_service_port_enabled() -> Optional[bool]:
    """服务端口开关是否打开。

    未开启是 CLI_TIMEOUT 的头号原因，能主动读出来就不必让用户猜。
    读不到返回 None（表示无法判断，而非"已关闭"）。
    """
    value = _read_first(".ide-status")
    if value is None:
        return None
    return value.strip().lower() == "on"
