from selectolax.parser import HTMLParser

from ..classify import infer_city, infer_job_type
from ..dateparse import guess_deadline
from .http import fetch


def parse_weixin(html: str) -> tuple[str, str]:
    tree = HTMLParser(html)
    title = ""
    h1 = tree.css_first("h1#activity-name") or tree.css_first("h1")
    if h1 is not None:
        title = h1.text(strip=True) or ""
    if not title:
        meta = tree.css_first("meta[property='og:title']")
        if meta is not None:
            title = (meta.attributes.get("content") or "").strip()
    body_node = tree.css_first("div#js_content") or tree.body
    body = body_node.text(separator="\n", strip=True) if body_node else ""
    return title.strip(), body


def build_draft(html: str, url: str) -> dict:
    title, body = parse_weixin(html)
    text = title + "\n" + body
    return {
        "title": title or "(无标题，请确认)",
        "url": url,
        "source_slug": "pastebox",
        "org": None,
        "city": infer_city(text),
        "job_type": infer_job_type(text),
        "publish_date": None,
        "deadline": guess_deadline(text),
        "body": body,
        "status": "pending",
        "needs_review": True,
    }


def collect_url(url: str) -> dict:
    r = fetch(url)
    return build_draft(r.text, url)
