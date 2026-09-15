from app.dedup import (date_compatible, is_same_job, is_same_title, merge_key,
                       normalize_url, title_fingerprint, url_fingerprint)


def test_normalize_strips_tracking():
    a = "https://mp.weixin.qq.com/s?abc=1&utm_source=x&from=y"
    b = "http://www.mp.weixin.qq.com/s?abc=1"
    assert normalize_url(a) == normalize_url(b)


def test_url_fingerprint_stable():
    assert url_fingerprint("https://a.cn/x/1?utm_source=t") == url_fingerprint("https://a.cn/x/1")


def test_title_fingerprint_ignores_punct():
    assert title_fingerprint("广州市中级人民法院", "招聘劳动合同制书记员（11人）") == \
           title_fingerprint("广州市中级 人民法院", "招聘劳动合同制书记员 11人")


def test_similarity_merge():
    a = title_fingerprint("佛山市律师协会", "广东华某某律师事务所招聘授薪律师")
    b = title_fingerprint("佛山市律师协会", "广东华某某律师事务所 招聘授薪律师")
    assert is_same_job(a, b)
    c = title_fingerprint("佛山市律师协会", "completely different job title here ok")
    assert not is_same_job(a, c)


def test_generic_short_titles_never_merge():
    """泛岗位名（律师助理 / 法务专员）在不同律所反复出现，绝不能合并。"""
    a = title_fingerprint("", "律师助理")
    b = title_fingerprint("", "律师助理")
    assert merge_key(a) is None
    assert not is_same_job(a, b)
    assert not is_same_job(title_fingerprint("", "法务专员"), title_fingerprint("", "法务专员"))


def test_date_compatible():
    assert date_compatible("2026-09-01", "2026-09-20")
    assert not date_compatible("2023-03-08", "2026-01-22")
    assert date_compatible(None, "2026-09-01")  # 缺日期不阻断合并


def test_route_fragment_kept_plain_anchor_dropped():
    """SPA hash 路由的标识在 fragment 里，必须保留；普通锚点要丢弃。"""
    a = url_fingerprint("https://jyzx.zuel.edu.cn/#/home/careerDetail?id=44154")
    b = url_fingerprint("https://jyzx.zuel.edu.cn/#/home/careerDetail?id=44153")
    assert a != b, "同站不同职位的 SPA 路由被当成同一条"

    assert url_fingerprint("https://a.cn/x/1#top") == url_fingerprint("https://a.cn/x/1#a1")


def test_same_job_from_two_sources_merges_by_title():
    """同一条招聘散落在两个渠道：URL 不同但单位+标题相同 → 应当合并。"""
    u1 = url_fingerprint("https://gdcourts.gov.cn/gsxx/post_1.html")
    u2 = url_fingerprint("https://hrss.gd.gov.cn/zwgk/post_9.html")
    assert u1 != u2
    assert is_same_job(
        title_fingerprint("广东省高级人民法院", "2026年公开招聘劳动合同制书记员公告"),
        title_fingerprint("广东省高级人民法院", "2026年公开招聘劳动合同制书记员公告"))
