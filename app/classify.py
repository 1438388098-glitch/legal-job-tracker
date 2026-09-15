import re

CITIES = ["广州", "深圳", "珠海", "佛山", "惠州", "东莞", "中山", "江门", "肇庆", "韶关"]

_RULES = [
    ("intern", re.compile(r"实习")),
    ("public", re.compile(r"法院|检察院|公务员|事业单位|书记员|法官助理|检察官助理|招录|警务辅助|审判辅助|国资|国企|编制")),
    ("lawfirm", re.compile(r"律师事务所|律所|执业律师|授薪律师|合伙人|律师助理")),
    ("legal_counsel", re.compile(r"法务|合规|法律顾问|风控")),
]


def infer_job_type(text: str) -> str:
    for key, pat in _RULES:
        if pat.search(text or ""):
            return key
    return "unknown"


def infer_city(text: str, default: str | None = None):
    for c in CITIES:
        if c in (text or ""):
            return c
    return default
