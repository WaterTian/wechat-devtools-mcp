"""
wechat_file 工具：文件读取聚合。

合并原 wechat_project_info、wechat_list_pages、wechat_read_page、wechat_read_file。
"""
import json
import os
from typing import TYPE_CHECKING

from ..core.cli import _resolve_project_path
from ..core.errors import ErrorCode
from ..models.schemas import WechatFileInput
from ..utils.response import _ok, _fail

if TYPE_CHECKING:
    from .._compat import FastMCP


# 这些文件按定义属于项目根，云开发项目的 miniprogram/ 下若有同名文件是非权威副本
_PROJECT_ROOT_FIRST_FILES: frozenset[str] = frozenset({
    "project.config.json",
    "project.private.config.json",
})


def register_file(mcp: "FastMCP") -> None:
    """将 wechat_file 工具注册到 FastMCP 实例。"""
    mcp.tool(
        name="wechat_file",
        annotations={
            "title": "项目文件读取",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )(wechat_file)


async def wechat_file(params: WechatFileInput) -> str:
    """读取小程序项目文件和结构信息。
    支持 action: project_info(项目完整信息), list_pages(页面列表),
    read_page(读取页面源码), read_file(读取单个文件)。
    返回 JSON: {success, data, message, error_code?}。
    """
    try:
        if params.action == "project_info":
            return await _action_project_info(params)
        elif params.action == "list_pages":
            return await _action_list_pages(params)
        elif params.action == "read_page":
            return await _action_read_page(params)
        elif params.action == "read_file":
            return await _action_read_file(params)
        return _fail(ErrorCode.UNKNOWN_ERROR, f"未知 action: {params.action}")
    except ValueError as e:
        return _fail(ErrorCode.PROJECT_PATH_MISSING, str(e))
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"执行失败：{type(e).__name__}: {e}")


def _get_miniprogram_root(proj: str) -> str:
    """从 project.config.json 解析 miniprogramRoot，默认返回 proj。"""
    config_path = os.path.join(proj, "project.config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            mp_root = config.get("miniprogramRoot", "")
            if mp_root:
                return os.path.join(proj, mp_root.rstrip("/\\"))
        except Exception:
            pass
    return proj


def _candidate_bases(proj: str) -> list[str]:
    """返回文件解析的候选根目录，按优先级排列。

    云开发项目（miniprogramRoot="miniprogram/"）里，页面和 app.json 在小程序根下，
    而 project.config.json、cloudfunctions/ 在项目根下，两者都要试。
    list_pages / project_info 一直按 miniprogramRoot 解析，read_page / read_file
    过去只按项目根解析，导致 list_pages 的输出喂给 read_page 必然读不到文件。

    Returns:
        [miniprogramRoot, proj]；两者相同时（普通项目）只返回一个。
    """
    mp_root = _get_miniprogram_root(proj)
    if os.path.abspath(mp_root) == os.path.abspath(proj):
        return [proj]
    return [mp_root, proj]


async def _action_project_info(params: WechatFileInput) -> str:
    """获取项目完整信息（config、app.json、目录结构）。"""
    proj = _resolve_project_path(params.project_path)
    data: dict = {"project_path": proj}

    config_path = os.path.join(proj, "project.config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data["project_config"] = json.load(f)
        except Exception as e:
            data["project_config_error"] = str(e)

    miniprogram_root = _get_miniprogram_root(proj)
    app_json_path = os.path.join(miniprogram_root, "app.json")
    if os.path.exists(app_json_path):
        try:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data["app_config"] = json.load(f)
        except Exception as e:
            data["app_config_error"] = str(e)

    for fname in ("app.wxss", "app.js"):
        fpath = os.path.join(miniprogram_root, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                limit = 100 if fname.endswith(".wxss") else 50
                data[fname] = "".join(lines[:limit])
            except Exception:
                pass

    # 目录结构
    dir_structure: list[dict] = []
    try:
        for item in sorted(os.listdir(proj)):
            if item.startswith(".") or item in ("node_modules", "miniprogram_npm", "__pycache__"):
                continue
            full = os.path.join(proj, item)
            if os.path.isdir(full):
                dir_structure.append({"name": item, "type": "dir", "children": len(os.listdir(full))})
            else:
                dir_structure.append({"name": item, "type": "file", "size": os.path.getsize(full)})
    except Exception:
        pass
    data["directory"] = dir_structure

    return _ok(data, message=f"项目信息读取成功：{proj}")


async def _action_list_pages(params: WechatFileInput) -> str:
    """列出 app.json 中注册的所有页面及其文件状态。"""
    proj = _resolve_project_path(params.project_path)
    miniprogram_root = _get_miniprogram_root(proj)
    app_json_path = os.path.join(miniprogram_root, "app.json")

    if not os.path.exists(app_json_path):
        return _fail(ErrorCode.UNKNOWN_ERROR, f"未找到 app.json：{app_json_path}")

    try:
        with open(app_json_path, "r", encoding="utf-8") as f:
            app_config = json.load(f)
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"读取 app.json 失败：{e}")

    pages = app_config.get("pages", [])
    if not pages:
        return _ok({"pages": [], "total": 0}, message="app.json 中未定义任何页面。")

    exts = [".wxml", ".wxss", ".js", ".json", ".ts"]
    pages_info: list[dict] = []
    for page in pages:
        page_base = os.path.join(miniprogram_root, page)
        existing = []
        missing = []
        for ext in exts:
            if os.path.exists(page_base + ext):
                existing.append({"ext": ext, "size": os.path.getsize(page_base + ext)})
            elif ext != ".ts":
                missing.append(ext)
        pages_info.append({
            "path": page,
            "complete": len(missing) == 0,
            "files": existing,
            "missing": missing,
        })

    return _ok({"pages": pages_info, "total": len(pages)}, message=f"共 {len(pages)} 个页面。")


async def _action_read_page(params: WechatFileInput) -> str:
    """读取指定页面的所有源码文件（.wxml/.wxss/.js/.json）。"""
    if not params.page_path:
        return _fail(ErrorCode.PARAM_MISSING, "action='read_page' 缺少必填参数: page_path")
    proj = _resolve_project_path(params.project_path)
    exts = [".wxml", ".wxss", ".js", ".json", ".ts"]

    # 依次在 miniprogramRoot、项目根下查找，与 list_pages 的路径口径保持一致
    files: dict[str, str] = {}
    tried: list[str] = []
    resolved_base = ""
    for base in _candidate_bases(proj):
        page_base = os.path.join(base, params.page_path)
        tried.append(f"{page_base}.*")
        for ext in exts:
            fpath = page_base + ext
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    files[os.path.basename(fpath)] = "".join(lines[:500])
                except Exception as e:
                    files[os.path.basename(fpath)] = f"读取失败：{e}"
        if files:
            resolved_base = base
            break

    if not files:
        return _fail(
            ErrorCode.UNKNOWN_ERROR,
            f"未找到页面文件：{'、'.join(tried)}",
            hint="请用 wechat_file(action='list_pages') 核对页面路径是否已在 app.json 注册。",
        )
    return _ok(
        {"page_path": params.page_path, "files": files, "resolved_base": resolved_base},
        message=f"读取页面 {params.page_path} 成功。",
    )


async def _action_read_file(params: WechatFileInput) -> str:
    """读取项目中的单个任意文件。"""
    if not params.file_path:
        return _fail(ErrorCode.PARAM_MISSING, "action='read_file' 缺少必填参数: file_path")
    proj = _resolve_project_path(params.project_path)

    # app.json 等在 miniprogramRoot 下，project.config.json / cloudfunctions/ 在项目根下，
    # 两个根都试一遍（普通项目二者相同，只试一次）
    bases = _candidate_bases(proj)
    # 工具链配置按定义就是项目根产物；云开发项目的 miniprogram/ 下可能另有一份同名文件
    # （内容不同、非权威），必须优先返回根目录那份
    if os.path.basename(params.file_path) in _PROJECT_ROOT_FIRST_FILES:
        bases = sorted(bases, key=lambda b: os.path.abspath(b) != os.path.abspath(proj))

    candidates = [os.path.join(base, params.file_path) for base in bases]
    existing = [p for p in candidates if os.path.isfile(p)]
    fpath = existing[0] if existing else ""

    if not fpath:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"文件不存在：{'、'.join(candidates)}")

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)
        content = "".join(lines[:800])
        data: dict = {
            "file_path": params.file_path,
            "resolved_path": fpath,
            "total_lines": total,
            "content": content,
            "truncated": total > 800,
        }
        msg = f"读取文件 {params.file_path} 成功（共 {total} 行）。"
        if len(existing) > 1:
            data["also_found_at"] = existing[1:]
            msg += f" ⚠ 另有 {len(existing) - 1} 处同名文件，详见 also_found_at。"
        return _ok(data, message=msg)
    except Exception as e:
        return _fail(ErrorCode.UNKNOWN_ERROR, f"读取文件失败：{e}")
