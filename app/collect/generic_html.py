import json
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..classify import infer_city, infer_job_type
from ..dateparse import guess_deadline, parse_date_text
from .http import fetch


def parse_list(html: str, cfg: dict) -> list[dict]:
    tree = HTMLParser(html)
    items = []
    for node in tree.css(cfg["item_sel"]):
        a = node.css_first(cfg.get("title_sel", "a"))
        if a is None or not a.attributes.get("href"):
            continue
        date_node = node.css_first(cfg["date_sel"]) if cfg.get("date_sel") else None
        items.append({
            "title": a.text(strip=True),
            "url": urljoin(cfg["list_url"], a.attributes["href"]),
            "publish_date": parse_date_text(date_node.text(strip=True)) if date_node else None,
        })
    return items


def extract_text(html: str, sel: str | None) -> str:
    tree = HTMLParser(html)
    node = tree.css_first(sel) if sel else None
    if node is None:
        node = tree.body
    return node.text(separator="\n", strip=True) if node else ""


def enrich(item: dict, body: str, cfg: dict) -> dict:
    item["body"] = body
    item["deadline"] = guess_deadline(body)
    item["job_type"] = cfg.get("job_type") or infer_job_type(item["title"])
    item["city"] = cfg.get("city") or infer_city(item["title"])
    item["org"] = cfg.get("org")
    return item


class Adapter:
    """配置驱动的静态列表适配器。config 字段见 docs/source-registry.md。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def collect(self) -> list[dict]:
        cfg = self.cfg
        r = fetch(cfg["list_url"], encoding=cfg.get("encoding"),
                  verify=cfg.get("verify", True))
        items = parse_list(r.text, cfg)[: cfg.get("max_items", 30)]
        out = []
        for it in items:
            try:
                d = fetch(it["url"], encoding=cfg.get("encoding"),
                          verify=cfg.get("verify", True))
                body = extract_text(d.text, cfg.get("detail_sel"))
            except Exception:  # noqa: BLE001 详情抓取失败不放弃该条
                body = ""
            out.append(enrich(it, body, cfg))
        return out


def adapter_from_source_row(row) -> Adapter:
    return Adapter(json.loads(row["config"] or "{}"))
