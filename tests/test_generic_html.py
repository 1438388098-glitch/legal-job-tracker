from pathlib import Path

from app.collect import generic_html

CFG = {
    "list_url": "https://www.gdcourts.gov.cn/gsxx/fayuangonggao/index.html",
    "item_sel": "ul.news-list li",
    "title_sel": "a",
    "date_sel": "span.date",
    "detail_sel": "div.article",
    "city": "广州",
}


def test_parse_list():
    html = Path("tests/fixtures/gdcourts_list.html").read_text("utf-8")
    items = generic_html.parse_list(html, CFG)
    assert len(items) == 2
    assert items[0]["title"].startswith("广东省高级人民法院")
    assert items[0]["url"] == \
        "https://www.gdcourts.gov.cn/gsxx/fayuangonggao/202609/t1202609011.html"
    assert items[0]["publish_date"] == "2026-09-01"


def test_parse_detail_and_fields():
    html = Path("tests/fixtures/gdcourts_detail.html").read_text("utf-8")
    body = generic_html.extract_text(html, "div.article")
    assert "2026年9月20日" in body
    item = generic_html.enrich(
        {"title": "广东省高级人民法院2026年公开招聘劳动合同制书记员公告",
         "url": "https://x/1", "publish_date": "2026-09-01"},
        body, CFG)
    assert item["deadline"] == "2026-09-20"
    assert item["job_type"] == "public"
    assert item["city"] == "广州"
