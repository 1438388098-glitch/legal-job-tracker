"""以真实录制的列表页 fixture 校验 27 个 html 源的选择器配置。

33 个源中其余 6 个非 html 源（frontpage/zuel/ggfw/hotjob/swupl）由各自专属测试覆盖
（如 test_zuel.py）。fixture 由 scripts/sync_fixtures.py 录制；选择器由
scripts/probe_sources.py 与 scripts/peek.py 对照真实页面校准。
任何源改版导致选择器失效时，本测试会失败。
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
    assert len(items) >= 2, f"{slug}: 仅 {len(items)} 条，选择器可能过窄"


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
            # 各 kind 的入口字段不同（zuel/ggfw=api，hotjob=api，swupl=list_url）
            keys = ("api", "list_url")
            assert any(str(cfg.get(k, "")).startswith("http") for k in keys), s["slug"]
        assert s["name"], s["slug"]


def test_campus_boards_query_by_law_keywords():
    """全专业职位板必须做筛选，否则会把无关岗位灌进来。

    广外/广大的详情页是 JS 渲染，拿不到专业字段，只能靠站内 ?keyword= 检索法学岗；
    但站内检索是模糊匹配（搜「法务」会带出会计专员、销售订单管理），
    所以必须再叠一层本地关键词过滤。
    """
    for slug in ("gdufs", "gzhu"):
        cfg = BY_SLUG[slug]["config"]
        urls = cfg["list_urls"]
        assert urls and all("keyword=" in u for u in urls), slug
        assert any("%E6%B3%95%E5%8A%A1" in u for u in urls), f"{slug}: 检索词里缺「法务」"
        assert cfg.get("keep_keywords"), f"{slug}: 缺本地关键词过滤"
    # 中南财接口的过滤在 zuel.py 内按"岗位名含法学角色词"完成
    # （该接口的 majors 字段会把企业所有专业列全，不能当过滤依据），覆盖见 tests/test_zuel.py


def test_sz_source_forces_http():
    """深圳人社 https 握手失败，必须按 http 拼详情 URL。"""
    assert BY_SLUG["hrss_sz"]["config"]["url_scheme"] == "http"
    cfg = BY_SLUG["hrss_sz"]["config"]
    items = generic_html.parse_list(_load("hrss_sz", cfg), cfg)
    assert items and all(i["url"].startswith("http://") for i in items)


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
