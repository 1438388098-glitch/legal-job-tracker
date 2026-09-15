from app.dedup import is_same_title, normalize_url, title_fingerprint, url_fingerprint


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
    assert is_same_title(a, b)
    c = title_fingerprint("佛山市律师协会", "completely different job title here ok")
    assert not is_same_title(a, c)
