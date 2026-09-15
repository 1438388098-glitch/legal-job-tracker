import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "spm", "from", "share_token", "chksm", "scene", "fromwb"}
_PUNCT = re.compile(r"[\s（）()\[\]【】「」·,，。.、:：;；!！?？\"'“”‘’\-—_~&]+")


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    netloc = p.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if k.lower() not in TRACKING_PARAMS])
    return urlunsplit(("http", netloc, p.path.rstrip("/") or "/", query, ""))


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def title_fingerprint(org: str, title: str) -> str:
    o = _PUNCT.sub("", org or "").lower()
    t = _PUNCT.sub("", title).lower()
    return f"{o}|{t[:60]}"


def is_same_title(fp_a: str, fp_b: str, threshold: float = 0.85) -> bool:
    return SequenceMatcher(None, fp_a, fp_b).ratio() >= threshold
