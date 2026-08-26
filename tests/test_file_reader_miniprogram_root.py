"""read_page / read_file 的路径口径必须与 list_pages 一致（云开发项目 miniprogramRoot）。

背景：list_pages / project_info 按 project.config.json 的 miniprogramRoot 解析，
而 read_page / read_file 直接按项目根解析。云开发项目（miniprogramRoot="miniprogram/"）里
list_pages 返回 "pages/home/index"，喂给 read_page 会解析到 <proj>/pages/home/index.*，
文件其实在 <proj>/miniprogram/pages/home/index.*，于是必然报"未找到页面文件"。
SKILL.md 的 SOP G 第一步正是这个组合。
"""
import json

import pytest

from wechat_devtools_mcp.models.schemas import WechatFileInput
from wechat_devtools_mcp.tools.file_reader import wechat_file


def _make_cloud_project(tmp_path):
    """构造云开发项目结构：miniprogramRoot=miniprogram/ + cloudfunctions/。"""
    (tmp_path / "project.config.json").write_text(
        json.dumps({"miniprogramRoot": "miniprogram/", "appid": "wxtest"}),
        encoding="utf-8",
    )
    mp = tmp_path / "miniprogram"
    (mp / "pages" / "home").mkdir(parents=True)
    (mp / "app.json").write_text(
        json.dumps({"pages": ["pages/home/index"]}), encoding="utf-8"
    )
    for ext, body in ((".wxml", "<view>home</view>"), (".js", "Page({})"),
                      (".json", "{}"), (".wxss", ".home{}")):
        (mp / "pages" / "home" / f"index{ext}").write_text(body, encoding="utf-8")
    (tmp_path / "cloudfunctions").mkdir()
    (tmp_path / "cloudfunctions" / "login.js").write_text("// login", encoding="utf-8")
    return tmp_path


def _make_plain_project(tmp_path):
    """构造普通项目结构：无 miniprogramRoot，页面直接在项目根下。"""
    (tmp_path / "project.config.json").write_text(
        json.dumps({"appid": "wxtest"}), encoding="utf-8"
    )
    (tmp_path / "pages" / "index").mkdir(parents=True)
    (tmp_path / "app.json").write_text(
        json.dumps({"pages": ["pages/index/index"]}), encoding="utf-8"
    )
    (tmp_path / "pages" / "index" / "index.wxml").write_text("<view/>", encoding="utf-8")
    (tmp_path / "pages" / "index" / "index.js").write_text("Page({})", encoding="utf-8")
    return tmp_path


class TestReadPageUnderMiniprogramRoot:
    @pytest.mark.asyncio
    async def test_read_page_resolves_under_miniprogram_root(self, tmp_path):
        """云开发项目的页面在 miniprogram/ 下，read_page 必须能读到。"""
        proj = _make_cloud_project(tmp_path)
        params = WechatFileInput(
            action="read_page", page_path="pages/home/index", project_path=str(proj)
        )
        result = json.loads(await wechat_file(params))
        assert result["success"] is True, result
        assert "index.wxml" in result["data"]["files"]
        assert "home" in result["data"]["files"]["index.wxml"]

    @pytest.mark.asyncio
    async def test_list_pages_output_feeds_read_page(self, tmp_path):
        """list_pages 返回的路径必须能直接喂给 read_page（两者口径一致）。"""
        proj = _make_cloud_project(tmp_path)
        listed = json.loads(await wechat_file(
            WechatFileInput(action="list_pages", project_path=str(proj))
        ))
        page_path = listed["data"]["pages"][0]["path"]

        read = json.loads(await wechat_file(
            WechatFileInput(action="read_page", page_path=page_path, project_path=str(proj))
        ))
        assert read["success"] is True, f"list_pages 给出 {page_path}，read_page 却读不到"

    @pytest.mark.asyncio
    async def test_plain_project_still_works(self, tmp_path):
        """无 miniprogramRoot 的普通项目不得回归。"""
        proj = _make_plain_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_page", page_path="pages/index/index",
                            project_path=str(proj))
        ))
        assert result["success"] is True
        assert "index.wxml" in result["data"]["files"]

    @pytest.mark.asyncio
    async def test_missing_page_still_fails(self, tmp_path):
        """页面确实不存在时仍应报错，不能因为多路径回退而误报成功。"""
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_page", page_path="pages/nope/index",
                            project_path=str(proj))
        ))
        assert result["success"] is False


class TestReadFileDualRoot:
    @pytest.mark.asyncio
    async def test_read_file_app_json_under_miniprogram_root(self, tmp_path):
        """app.json 在 miniprogram/ 下（SKILL.md 的示例用法）。"""
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="app.json", project_path=str(proj))
        ))
        assert result["success"] is True, result
        assert "pages/home/index" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_file_project_config_at_project_root(self, tmp_path):
        """project.config.json 在项目根，不能因为改走 miniprogramRoot 而读不到。"""
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="project.config.json",
                            project_path=str(proj))
        ))
        assert result["success"] is True, result
        assert "miniprogramRoot" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_file_cloudfunctions_at_project_root(self, tmp_path):
        """cloudfunctions/ 也在项目根下。"""
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="cloudfunctions/login.js",
                            project_path=str(proj))
        ))
        assert result["success"] is True, result

    @pytest.mark.asyncio
    async def test_read_file_missing_still_fails(self, tmp_path):
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="nope.json", project_path=str(proj))
        ))
        assert result["success"] is False


class TestReadFileAmbiguity:
    """同名文件在两个根下都存在时，不能静默挑一个就完事（云开发项目实测存在
    两份内容不同的 project.config.json）。"""

    @pytest.mark.asyncio
    async def test_project_config_prefers_project_root(self, tmp_path):
        """project.config.json 按定义就是项目根产物，权威的是根目录那份。"""
        proj = _make_cloud_project(tmp_path)
        (proj / "miniprogram" / "project.config.json").write_text(
            json.dumps({"setting": {"es6": False}}), encoding="utf-8"
        )
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="project.config.json",
                            project_path=str(proj))
        ))
        assert result["success"] is True
        assert result["data"]["resolved_path"] == str(proj / "project.config.json")
        assert "miniprogramRoot" in result["data"]["content"]
        assert "also_found_at" in result["data"]

    @pytest.mark.asyncio
    async def test_duplicate_file_reports_ambiguity(self, tmp_path):
        """普通同名文件仍按 miniprogramRoot 优先，但要如实报告另一处。"""
        proj = _make_cloud_project(tmp_path)
        (proj / "config.json").write_text('{"where":"root"}', encoding="utf-8")
        (proj / "miniprogram" / "config.json").write_text('{"where":"mp"}', encoding="utf-8")
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="config.json", project_path=str(proj))
        ))
        assert result["success"] is True
        assert result["data"]["resolved_path"] == str(proj / "miniprogram" / "config.json")
        assert result["data"]["also_found_at"] == [str(proj / "config.json")]

    @pytest.mark.asyncio
    async def test_unique_file_has_no_ambiguity_field(self, tmp_path):
        proj = _make_cloud_project(tmp_path)
        result = json.loads(await wechat_file(
            WechatFileInput(action="read_file", file_path="app.json", project_path=str(proj))
        ))
        assert result["success"] is True
        assert "also_found_at" not in result["data"]
