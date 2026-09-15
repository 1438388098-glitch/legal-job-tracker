import hashlib
import re
from datetime import date
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "spm", "from", "share_token", "chksm", "scene", "fromwb"}
_PUNCT = re.compile(r"[\s（）()\[\]【】「」·,，。.、:：;；!！?？\"'“”‘’\-—_~&]+")
# SPA 的 hash 路由（如中南财就业网 /#/home/careerDetail?id=44154）把标识放在
# fragment 里，丢掉它会让整站条目指纹相同、只能入库一条。普通锚点（#top、#a1）仍丢弃。
_ROUTE_FRAG = re.compile(r"[/=?&]")


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    netloc = p.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if k.lower() not in TRACKING_PARAMS])
    frag = p.fragment if _ROUTE_FRAG.search(p.fragment) else ""
    return urlunsplit(("http", netloc, p.path.rstrip("/") or "/", query, frag))


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def title_fingerprint(org: str, title: str) -> str:
    o = _PUNCT.sub("", org or "").lower()
    t = _PUNCT.sub("", title).lower()
    return f"{o}|{t[:60]}"


def is_same_title(fp_a: str, fp_b: str, threshold: float = 0.95) -> bool:
    return SequenceMatcher(None, fp_a, fp_b).ratio() >= threshold


# ── 跨源合并规则 ────────────────────────────────────────────────────────
# 背景：同一场招聘常常同时挂在省法院、省人社厅、律协等多个渠道，需要合成一条。
# 但"标题像"就合并会误伤，实测踩到三类坑：
#   1. 同一批公告的不同期次（中山某镇招聘公示 6 期）被合成一条 —— 同源不合并；
#   2. 不同年份的同名公告（检察院 2023/2024/2025 选调公告）被合成一条 —— 同源不合并；
#   3. 泛岗位名（"律师助理"、"法务专员"）在不同律所反复出现 —— 不能只看标题。
# 因此合并键 = 单位|标题：单位不同则键必然不同，泛岗位名天然不会撞在一起；
# 只有单位为空且标题又短（信息太少）的才放弃合并。
MIN_MERGE_TITLE_LEN = 10
DATE_TOLERANCE_DAYS = 45


def _title_part(fp: str) -> str:
    return (fp or "").partition("|")[2]


def merge_key(fp: str) -> str | None:
    """可用于跨源合并的键 = 单位|标题。

    键里带单位后，"不同律所的律师助理"不会再被误合并（单位不同 → 键不同）；
    真正无法安全合并的只剩"单位也为空、标题又短"——两条信息都凑不齐，
    合了大概率是错的。曾经标题<10 字一律不合并，结果同一岗位挂在两个高校
    就业网上（各单位名齐全）永远合不上，用户会看到两张一模一样的卡片。
    """
    org, _, t = (fp or "").partition("|")
    if not t:
        return None
    if not org and len(t) < MIN_MERGE_TITLE_LEN:
        return None
    return f"{org}|{t}"


def date_compatible(a: str | None, b: str | None,
                    tol: int = DATE_TOLERANCE_DAYS) -> bool:
    """两条记录发布时间是否接近。任一方缺失视为兼容（不阻断合并）。"""
    if not a or not b:
        return True
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= tol
    except ValueError:
        return True


def is_same_job(fp_a: str, fp_b: str) -> bool:
    """跨源同一场招聘的判定：两边标题都要够长，且完全相同或高度相似。"""
    ka, kb = merge_key(fp_a), merge_key(fp_b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    return is_same_title(fp_a, fp_b)
