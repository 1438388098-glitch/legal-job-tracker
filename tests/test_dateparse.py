from datetime import date

from app.dateparse import extract_dates, guess_deadline, parse_date_text


def test_full_dates():
    assert extract_dates("2026年3月20日") == ["2026-03-20"]
    assert extract_dates("2026-03-20至2026-04-01") == ["2026-03-20", "2026-04-01"]
    assert extract_dates("2026.3.20 / 2026/4/1") == ["2026-03-20", "2026-04-01"]


def test_ymd_infer_year():
    assert extract_dates("报名截止时间：3月20日", today=date(2026, 3, 1)) == ["2026-03-20"]
    assert extract_dates("12月30日截止", today=date(2026, 1, 5)) == ["2026-12-30"]


def test_invalid_ignored():
    assert extract_dates("2月30日") == []


def test_guess_deadline_is_anchored_to_deadline_words():
    """只在"截止/报名时间"等词附近取日期，不能拿全篇最大日期当截止。"""
    assert guess_deadline("2026年3月1日发布，报名截止时间3月20日17:00") == "2026-03-20"
    assert guess_deadline("报名时间为2026年9月1日至2026年9月10日") == "2026-09-10"
    assert guess_deadline("请于2026年9月20日前将材料发送至邮箱") == "2026-09-20"
    assert guess_deadline("无任何日期") is None
    assert guess_deadline("") is None


def test_guess_deadline_ignores_unrelated_later_dates():
    """体检/考试日期在截止日之后，不能被当成截止日。"""
    text = ("报名截止时间：2026年9月10日。"
            "笔试时间：2026年10月15日。体检时间：2026年11月20日。")
    assert guess_deadline(text) == "2026-09-10"


def test_guess_deadline_none_when_no_deadline_context():
    """只有发布日期、没有截止表述时，宁可返回空也不给假截止日。"""
    assert guess_deadline("本公告于2026年9月1日发布，欢迎关注。") is None


def test_parse_date_text_list_page():
    assert parse_date_text("2026-09-11") == "2026-09-11"
    assert parse_date_text("2026年9月11日") == "2026-09-11"
    assert parse_date_text("[09-11]", ) in (f"{date.today().year}-09-11", None)
    assert parse_date_text("") is None
