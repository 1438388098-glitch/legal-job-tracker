"""快照结构化视图的回归测试。

用真实公告的典型结构当样例（一、二小节 + 关键信息句），保证：
1. 小节标题被识别为 h1/h2，长句不误判；
2. 截止/联系方式等关键行进卡片；
3. HTML 已转义（快照来自外网，绝不能直接注入页面）。
"""
from app.web.snapshot_view import render_snapshot

SAMPLE = """广东省高级人民法院公开招聘劳动合同制书记员公告

一、招聘名额
共招聘15名，另确定15名递补人选。

二、招聘条件
1.具有中华人民共和国国籍；
4.普通高等学校法律类专业本科以上（非在职）毕业生；

三、报名方式
报名时间：2026年9月20日9:00至9月26日17:00。
咨询电话：020-12345678。
<script>alert(1)</script>
"""


def test_headings_detected():
    out = render_snapshot(SAMPLE)
    assert "snap-h1" in out["html"]
    assert "<h4 class='snap-h1'>一、招聘名额</h4>" in out["html"]
    assert "<h4 class='snap-h1'>三、报名方式</h4>" in out["html"]


def test_key_info_extracted():
    out = render_snapshot(SAMPLE)
    joined = " ".join(out["key"])
    assert "报名时间" in joined
    assert "咨询电话" in joined
    assert any("本科" in k for k in out["key"])   # 学历要求进卡


def test_html_escaped():
    out = render_snapshot(SAMPLE)
    assert "<script>" not in out["html"]
    assert "&lt;script&gt;" in out["html"]


def test_empty_and_long_lines_safe():
    assert render_snapshot("") == {"key": [], "html": ""}
    long = "一、" + "很" * 60      # 超过 40 字的"一、"行不是标题
    out = render_snapshot(long)
    assert "snap-h1" not in out["html"]
