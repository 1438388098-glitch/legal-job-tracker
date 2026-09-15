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
#   3. 泛岗位名（"律师助理"、"法务专员"）在不同律所反复出现 —— 短标题不合并。
# 因此只有：跨源 + 标题够长 + 高度相似 + 发布时间接近，四个条件同时满足才合并。
MIN_MERGE_TITLE_LEN = 10
DATE_TOLERANCE_DAYS = 45


def _title_part(fp: str) -> str:
    return (fp or "").partition("|")[2]


def merge_key(fp: str) -> str | None:
    """可用于跨源合并的标题键；标题太短（泛岗位名）返回 None。"""
    t = _title_part(fp)
    return t if len(t) >= MIN_MERGE_TITLE_LEN else None


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
