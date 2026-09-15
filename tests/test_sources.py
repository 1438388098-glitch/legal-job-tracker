"""以真实录制的列表页 fixture 校验 13 个源的选择器配置。

fixture 由 scripts/sync_fixtures.py 录制；选择器由 scripts/probe_sources.py
与 scripts/peek.py 对照真实页面校准。任何源改版导致选择器失效时，本测试会失败。
"""
from datetime import date
from pathlib import Path

import pytest

from app.collect import generic_html
from scripts.seed_sources import SOURCES, _idx, _q

BY_SLUG = {s["slug"]: s for s in SOURCES}
HTML_SLUGS = [s["slug"] for s in SOURCES if s["kind"] == "html"]

NAV_JUNK = {"首页", "上一页", "下一页", "更多", "返回", "网站地图", "联系我们"}
FIXTURE_DAY = date(2026, 9, 15)  # fixture 录制基准日（见 docs/source-registry.md）


def _load(slug: str, cfg: dict) -> str:
    raw = Path(f"tests/fixtures/{slug}_list.html").read_bytes()
    for enc in (cfg.get("encoding"), "utf-8", "gb18030", "latin-1"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise AssertionError(f"{slug}: fixture 无法解码")


@pytest.mark.parametrize("slug", HTML_SLUGS)
def test_list_fixture_parses(slug):
    fx = Path(f"tests/fixtures/{slug}_list.html")
    if not fx.exists():
        pytest.skip(f"{slug} fixture 未录制（源当次不可达，见 source-registry）")
    cfg = BY_SLUG[slug]["config"]
    items = generic_html.parse_list(_load(slug, cfg), cfg)
    assert items, f"{slug}: 解析为 0 条，选择器需重新校准（scripts/probe_sources.py）"
    for i in items:
        assert i["title"] and len(i["title"]) >= 2, f"{slug}: 标题异常 {i['title']!r}"
        assert i["title"] not in NAV_JUNK, f"{slug}: 选择器把导航项当成条目 {i['title']!r}"
        assert i["url"].startswith("http"), f"{slug}: URL 拼接异常 {i['url']!r}"


@pytest.mark.parametrize("slug", HTML_SLUGS)
def test_list_fixture_yields_enough(slug):
    """每个源至少解析出 5 条，否则视为选择器过窄（会漏掉岗位）。"""
    fx = Path(f"tests/fixtures/{slug}_list.html")
    if not fx.exists():
        pytest.skip(f"{slug} fixture 未录制")
    cfg = BY_SLUG[slug]["config"]
    items = generic_html.parse_list(_load(slug, cfg), cfg)
    assert len(items) >= 5, f"{slug}: 仅 {len(items)} 条，选择器可能过窄"


@pytest.mark.parametrize("slug", HTML_SLUGS)
def test_noise_filters_keep_enough(slug):
    """噪音过滤后不得把该源清空（exclude_url/超龄/关键词规则别写太狠）。

    阈值只要求"还剩条目"：韶关人社这类综合栏目本身招聘稿件就稀疏（每页约 2 条），
    过滤后条数少是正常的，选择器过窄的问题由上一个用例（原始 >= 5）负责把关。
    fixture 录制于 FIXTURE_DAY，用固定基准日，避免测试随真实日期推移而失效。
    """
    fx = Path(f"tests/fixtures/{slug}_list.html")
    if not fx.exists():
        pytest.skip(f"{slug} fixture 未录制")
    cfg = BY_SLUG[slug]["config"]
    items = generic_html.apply_noise_filters(
        generic_html.parse_list(_load(slug, cfg), cfg), cfg, today=FIXTURE_DAY)
    assert items, f"{slug}: 过滤后为空，规则过严（exclude_url / max_age_days / title_keywords）"


def test_all_sources_have_required_config():
    for s in SOURCES:
        cfg = s["config"]
        if s["kind"] == "html":
            assert cfg["list_url"].startswith("http"), s["slug"]
            assert cfg["item_sel"], s["slug"]
        else:
            assert cfg["api"].startswith("http"), s["slug"]
        assert s["name"], s["slug"]


def test_campus_boards_are_keyword_filtered():
    """全专业职位板必须带法学过滤，否则会把无关岗位灌进来。"""
    for slug in ("gdufs", "gzhu", "zuel"):
        assert BY_SLUG[slug]["config"]["keep_keywords"], slug
        assert "法学" in BY_SLUG[slug]["config"]["keep_keywords"]


def test_zuel_in_seed():
    assert BY_SLUG["zuel"]["kind"] == "zuel"
    assert BY_SLUG["zuel"]["config"]["api"].startswith("https://jyzx.zuel.edu.cn")


def test_pagination_helpers():
    assert _idx("https://x/index.html", 3) == [
        "https://x/index.html", "https://x/index_2.html", "https://x/index_3.html"]
    assert _q("https://x/list", "page", 2) == [
        "https://x/list", "https://x/list?page=2"]
    assert _q("https://x/list?a=1", "p", 2) == [
        "https://x/list?a=1", "https://x/list?a=1&p=2"]


def test_no_source_has_duplicate_slug():
    slugs = [s["slug"] for s in SOURCES]
    assert len(slugs) == len(set(slugs))
