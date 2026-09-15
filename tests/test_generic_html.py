from app.collect import generic_html

LIST_HTML = """
<html><body>
<ul class="nav"><li><a href="/">首页</a></li></ul>
<ul class="list">
  <li><a href="/a/1.html" title="广东某法院2026年招聘书记员公告">
      广东某法院2026年招聘书记员公告…</a><span class="time">2026-09-01</span></li>
  <li><a href="/a/2.html" title="关于某项工作的通知">
      关于某项工作的通知</a><span class="time">2026-08-20</span></li>
</ul>
<div class="boards">
  <div class="jobs-list">
    <div class="col-xs-6"><a class="job-block" href="/job?id=9">
      <div class="job-name">管培生</div>
      <div class="job-time">09/03 发布</div>
      <div class="job-company">某律所</div></a></div>
  </div>
</div>
<div class="recruit">
  <a href="/recruit/details.html?id=1" title="广东培正律师事务所">
    <div>广东培正律师事务所</div><div>有多个热门职位等着您 ></div></a>
</div>
</body></html>
"""

BASE = {"list_url": "https://x.cn/list/index.html"}


def test_title_attr_and_date():
    cfg = dict(BASE, item_sel="ul.list li", title_attr="title", date_sel="span.time")
    items = generic_html.parse_list(LIST_HTML, cfg)
    assert len(items) == 2
    # title 属性优先：拿到完整标题，而不是页面上被"…"截断的可见文本
    assert items[0]["title"] == "广东某法院2026年招聘书记员公告"
    assert items[0]["url"] == "https://x.cn/a/1.html"
    assert items[0]["publish_date"] == "2026-09-01"


def test_relative_url_and_nav_excluded():
    cfg = dict(BASE, item_sel="ul.list li", date_sel="span.time")
    items = generic_html.parse_list(LIST_HTML, cfg)
    assert all("首页" not in i["title"] for i in items)
    assert items[0]["url"].startswith("https://x.cn/")


def test_link_sel_title_sel_org_sel():
    cfg = dict(BASE, item_sel="div.jobs-list div.col-xs-6", link_sel="a.job-block",
               title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company")
    items = generic_html.parse_list(LIST_HTML, cfg)
    assert len(items) == 1
    assert items[0]["title"] == "管培生"
    assert items[0]["org"] == "某律所"
    assert items[0]["url"] == "https://x.cn/job?id=9"
    assert items[0]["publish_date"].endswith("-09-03")


def test_link_sel_self():
    cfg = dict(BASE, item_sel='div.recruit a[href*="recruit/details"]',
               link_sel="self", title_attr="title")
    items = generic_html.parse_list(LIST_HTML, cfg)
    assert len(items) == 1
    assert items[0]["title"] == "广东培正律师事务所"
    assert items[0]["url"] == "https://x.cn/recruit/details.html?id=1"


def test_extract_text_and_enrich():
    html = "<html><body><div class='article'><p>报名截止2026年9月20日</p></div></body></html>"
    body = generic_html.extract_text(html, "div.article")
    assert "2026年9月20日" in body
    item = generic_html.enrich(
        {"title": "广东省高级人民法院2026年公开招聘劳动合同制书记员公告",
         "url": "https://x/1", "publish_date": "2026-09-01"},
        body, dict(BASE, city="广州", job_type="public"))
    assert item["deadline"] == "2026-09-20"
    assert item["job_type"] == "public"
    assert item["city"] == "广州"


def test_extract_text_fallback_to_body():
    html = "<html><body><p>正文内容</p></body></html>"
    assert "正文内容" in generic_html.extract_text(html, None)
    assert "正文内容" in generic_html.extract_text(html, "div.notexist")


def test_matches_keywords():
    assert generic_html.matches_keywords("某公司法务岗", ["法务", "律师"])
    assert generic_html.matches_keywords("Legal Counsel", ["legal"])
    assert not generic_html.matches_keywords("销售业务员", ["法务", "律师"])
    assert generic_html.matches_keywords("任意", [])  # 空关键词 = 全通过


def test_parse_list_dedupes_url():
    """嵌套表格会让同一条目被多个 tr 命中，必须按 URL 去重。"""
    html = """
    <table><tr><td><table><tr>
      <td><a href="/a/1.html">某法院招聘公告</a></td>
    </tr></table></td></tr></table>"""
    items = generic_html.parse_list(html, dict(BASE, item_sel="tr"))
    assert len(items) == 1


def test_noise_filters_drop_stale_and_excluded():
    items = [
        {"title": "陈年须知", "url": "https://x.cn/old", "publish_date": "2019-10-18"},
        {"title": "网上报名须知", "url": "https://x.cn/sydwzpwsbm/p1", "publish_date": None},
        {"title": "今年招聘公告", "url": "https://x.cn/new", "publish_date": "2026-09-01"},
    ]
    cfg = dict(BASE, exclude_url=["sydwzpwsbm"])
    kept = generic_html.apply_noise_filters(items, cfg)
    assert [i["title"] for i in kept] == ["今年招聘公告"]
    # 关闭超龄过滤后，仅按 exclude_url 过滤
    kept = generic_html.apply_noise_filters(items, dict(cfg, max_age_days=0))
    assert [i["title"] for i in kept] == ["陈年须知", "今年招聘公告"]


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def json(self):
        return {}


def _fake_fetch(list_html, detail_by_url):
    """list_url 返回列表页，其余 URL 返回对应详情页。"""
    def fetch(url, **kw):
        return _FakeResp(detail_by_url.get(url, list_html))
    return fetch


BOARD_HTML = """
<div class="jobs-list">
  <div class="col-xs-6"><a class="job-block" href="/job?id=1">
    <div class="job-name">管培生</div></a></div>
  <div class="col-xs-6"><a class="job-block" href="/job?id=2">
    <div class="job-name">销售业务员</div></a></div>
</div>"""
BOARD_CFG = dict(BASE, item_sel="div.jobs-list div.col-xs-6", link_sel="a.job-block",
                 title_sel="div.job-name")


def test_keep_keywords_filters_by_body(monkeypatch):
    """校园职位板：标题是"管培生"，法学信息只在正文专业要求里，也要能留下。"""
    monkeypatch.setattr(generic_html, "fetch", _fake_fetch(BOARD_HTML, {
        "https://x.cn/job?id=1": "<p>专业要求：法学类</p>",
        "https://x.cn/job?id=2": "<p>专业不限</p>",
    }))
    out = generic_html.Adapter(dict(BOARD_CFG, keep_keywords=["法学"])).collect()
    assert [i["title"] for i in out] == ["管培生"]


def test_collect_skips_known_urls(monkeypatch):
    """增量采集：已知 URL 不再重复抓详情。"""
    monkeypatch.setattr(generic_html, "fetch",
                        _fake_fetch(BOARD_HTML, {}))
    from app.dedup import url_fingerprint
    known = {url_fingerprint("https://x.cn/job?id=1")}
    out = generic_html.Adapter(BOARD_CFG).collect(known)
    assert [i["title"] for i in out] == ["销售业务员"]
