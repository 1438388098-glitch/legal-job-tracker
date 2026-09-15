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


def test_guess_deadline_takes_latest():
    assert guess_deadline("2026年3月1日发布，3月20日17:00前报名") == "2026-03-20"
    assert guess_deadline("无任何日期") is None


def test_parse_date_text_list_page():
    assert parse_date_text("2026-09-11") == "2026-09-11"
    assert parse_date_text("2026年9月11日") == "2026-09-11"
    assert parse_date_text("[09-11]", ) in (f"{date.today().year}-09-11", None)
    assert parse_date_text("") is None
