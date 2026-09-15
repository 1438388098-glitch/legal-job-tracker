import json
from urllib.parse import urljoin

from ..classify import infer_job_type
from ..dateparse import parse_date_text
from .http import fetch


def parse_payload(data: dict, base: str) -> list[dict]:
    rows = (data or {}).get("data") or []
    out = []
    for r in rows:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        rid = r.get("id")
        url = urljoin(base, f"/#/home/careerDetail?id={rid}") if rid else urljoin(base, "/#/home/career")
        majors = str(r.get("majors") or "")
        out.append({
            "title": title,
            "org": r.get("companyName"),
            "url": url,
            "deadline": parse_date_text(str(r.get("validTime") or "")),
            "publish_date": parse_date_text(str(r.get("createTime") or "")),
            "city": None,
            "job_type": infer_job_type(title + " " + majors),
            "body": json.dumps(r, ensure_ascii=False),
        })
    return out


class Adapter:
    """中南财经政法大学就业中心 JSON 接口适配器（免登录，已验证）。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api = cfg.get("api", "https://jyzx.zuel.edu.cn/api/publicly/recruit/list")
        self.base = cfg.get("base", "https://jyzx.zuel.edu.cn")
        self.rtype = cfg.get("type", 1)
        self.pages = int(cfg.get("pages", 3))
        self.limit = int(cfg.get("limit", 20))

    def collect(self) -> list[dict]:
        out = []
        for page in range(1, self.pages + 1):
            r = fetch(self.api, params={"page": page, "limit": self.limit, "type": self.rtype})
            items = parse_payload(r.json(), self.base)
            if not items:
                break
            out.extend(items)
        return out
