import re
from datetime import date, timedelta

_FULL = re.compile(r"(20\d{2})[年\-/.](\d{1,2})[月\-/.](\d{1,2})日?")
_SHORT = re.compile(r"(?<![\d年\-/.])(\d{1,2})月(\d{1,2})日")
_MD = re.compile(r"(?<![\d年\-/.])(\d{1,2})-(\d{1,2})(?![\d\-/.年])")
# 校园职位板常见 "09/03 发布" 这类省略年份的写法；要求两侧均为两位数字，
# 避免把 "1/2" 之类的比例误判成日期。
_MD_SLASH = re.compile(r"(?<![\d/\-.年])(\d{2})/(\d{2})(?![\d/\-.])")


def _valid(y, m, d):
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False


def extract_dates(text: str, today: date | None = None) -> list[str]:
    today = today or date.today()
    out = []
    for m in _FULL.finditer(text or ""):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if _valid(y, mo, d):
            out.append(date(y, mo, d).isoformat())
    for pat in (_SHORT, _MD, _MD_SLASH):
        for m in pat.finditer(text or ""):
            mo, d = int(m[1]), int(m[2])
            if not _valid(today.year, mo, d):
                continue
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=180):
                dt = date(today.year + 1, mo, d)
            out.append(dt.isoformat())
    return sorted(set(out))


def parse_date_text(text: str) -> str | None:
    dates = extract_dates(text)
    return dates[0] if dates else None


def guess_deadline(text: str, today: date | None = None) -> str | None:
    dates = extract_dates(text, today)
    return dates[-1] if dates else None
