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


# 某些 CMS 把年月和日拆在两个节点里，取父节点文本会得到 "2026-09 04"（年月在前）
# 或 "15 2026-09"（日在前，如中山律协/广东能源）。归一化成完整日期再走常规解析，
# 省得每个源写特殊逻辑。
_SPLIT_DATE = re.compile(r"((?:19|20)\d{2})\s*[-年/.]\s*(\d{1,2})\s*[-月/.]?\s+(\d{1,2})\s*日?")
_SPLIT_DATE_REV = re.compile(
    r"(?<!\d)(\d{1,2})\s+((?:19|20)\d{2})\s*[-年/.]\s*(\d{1,2})(?!\d)")


# 西北政法把"09月15日"拆进两个 <p>：'09月' 与 '15日'，取父节点文本得 '09月 15日'。
# 月与日被空白隔开，常规 _SHORT 匹配不到（它要求"月日"紧邻）。
_JOIN_MD = re.compile(r"(?<!\d)(\d{1,2})\s*月\s+(\d{1,2})\s*日")


def _normalize(text: str) -> str:
    t = _SPLIT_DATE.sub(lambda m: f"{m[1]}-{int(m[2])}-{int(m[3])}", text or "")
    t = _SPLIT_DATE_REV.sub(lambda m: f"{m[2]}-{int(m[3])}-{int(m[1])}", t)
    return _JOIN_MD.sub(lambda m: f"{int(m[1])}月{int(m[2])}日", t)


def extract_dates(
    text: str, today: date | None = None, year_hint: int | None = None
) -> list[str]:
    """year_hint：文本内已有完整年份时，省略年份的日期锚定到该年份，而非按
    "下一个未来日期"推断——公告里的发布年份就是省略年份的所指年份。"""
    today = today or date.today()
    text = _normalize(text)
    out = []
    for m in _FULL.finditer(text or ""):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if _valid(y, mo, d):
            out.append(date(y, mo, d).isoformat())
    for pat in (_SHORT, _MD, _MD_SLASH):
        for m in pat.finditer(text or ""):
            mo, d = int(m[1]), int(m[2])
            if year_hint is not None and _valid(year_hint, mo, d):
                out.append(date(year_hint, mo, d).isoformat())
                continue
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


# ── 截止日期推断 ────────────────────────────────────────────────────────
# 只取"截止"相关词附近窗口内的日期，而不是整篇公告里最大的那个日期。
# 早期版本取全篇最大日期，实测经常把体检时间、考试时间、甚至"年龄截止至报名开始当天"
# 当成投递截止，产生假的红色临期提醒——错误的截止日比没有截止日更糟。
_CTX_KEY = re.compile(
    r"(截止|截至|止于|报名时间|报名期限|报名日期|投递时间|投递截止|"
    r"申请时间|受理时间|起止时间|报名截止|接收时间|投递期限)")
# 取"截止"词所在整句（按句读切分，不按换行——公告常在半句处折行）。
# 不切句就会把后一句的"笔试时间/体检时间"一起吃进来，推断出错误的截止日。
_SENT_END = "。；;！？!?"


def _sentence_at(text: str, pos: int) -> str:
    start = 0
    for ch in _SENT_END:
        start = max(start, text.rfind(ch, 0, pos) + 1)
    end = len(text)
    for ch in _SENT_END:
        i = text.find(ch, pos)
        if i != -1:
            end = min(end, i)
    return text[start:end]


# "9月20日前" / "2026年9月20日之前" 这类没有"截止"二字的写法
_BEFORE_DATE = re.compile(
    r"(20\d{2}[年\-/.]\d{1,2}[月\-/.]\d{1,2}日?|\d{1,2}月\d{1,2}日)\s*(?:之前|以前|前)")


def guess_deadline(text: str, today: date | None = None) -> str | None:
    if not text:
        return None
    found: list[str] = []
    for m in _CTX_KEY.finditer(text):
        sent = _sentence_at(text, m.start())
        hint_m = _FULL.search(sent)
        found.extend(
            extract_dates(sent, today, int(hint_m[1]) if hint_m else None))
    for m in _BEFORE_DATE.finditer(text):
        found.extend(extract_dates(m.group(0), today))
    return max(found) if found else None
