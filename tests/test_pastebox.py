from pathlib import Path

from app.collect import pastebox


def test_build_draft_from_weixin_html():
    html = Path("tests/fixtures/weixin.html").read_text("utf-8")
    draft = pastebox.build_draft(html, "https://mp.weixin.qq.com/s/abc")
    assert draft["title"] == "广州某律师事务所招聘实习律师若干名"
    assert draft["body"] and "报名" in draft["body"]
    assert draft["status"] == "pending" and draft["needs_review"]
    assert draft["url"] == "https://mp.weixin.qq.com/s/abc"
    assert draft["deadline"] == "2026-10-08"
