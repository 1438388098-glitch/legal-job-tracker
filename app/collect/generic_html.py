import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from ..classify import (extract_org, infer_city, infer_employment_type,
                        infer_job_type, infer_notice_kind, is_rolling)
from ..dateparse import guess_deadline, parse_date_text
from ..dedup import url_fingerprint
from .http import fetch

log = logging.getLogger("collect")

# 列表页配置字段（全部可选，除 list_url/item_sel）：
#   item_sel    条目容器选择器
#   link_sel    条目内提供 href 的元素，默认 "a"；填 "self" 表示条目本身即 <a>
#   title_sel   条目内提供标题文本的元素，默认取 link_sel 的文本
#   title_attr  优先取该属性作为标题（如 "title"，可避免"…"截断与附属文案）
#   date_sel    条目内提供发布日期的元素
#   org_sel     条目内提供单位名的元素
#   detail_sel  详情页正文容器，留空则取 <body> 全文
#   max_items   单次抓取条数上限，默认 30
#   encoding / verify  编码与证书校验（政务站常见 gb2312 / 自签证书）


def _text(node) -> str:
    if node is None:
        return ""
    for sep in ("\n", " "):
        t = node.text(separator=sep, strip=True)
        if t:
            return t
    return ""


def apply_url_scheme(url: str, cfg: dict) -> str:
    """把条目 URL 强制切到指定协议（如 url_scheme="http"）。

    深圳人社详情页的 https 在 OpenSSL 3 下握手失败（BAD_ECPOINT），http 正常，
    列表页里却是绝对 https 链接，只能在解析阶段改写协议。
    """
    scheme = cfg.get("url_scheme")
    if not scheme:
        return url
    p = urlsplit(url)
    if p.scheme == scheme:
        return url
    return urlunsplit((scheme, p.netloc, p.path, p.query, p.fragment))


def parse_list(html: str, cfg: dict) -> list[dict]:
    tree = HTMLParser(html)
    link_sel = cfg.get("link_sel", "a")
    items, seen = [], set()
    for node in tree.css(cfg["item_sel"]):
        link = node if link_sel == "self" else node.css_first(link_sel)
        if link is None or not link.attributes.get("href"):
            continue
        url = urljoin(cfg["list_url"], link.attributes["href"])
        url = apply_url_scheme(url, cfg)
        if url in seen:
            continue  # 嵌套表格会让同一条目被多个 tr 命中，按 URL 去重

        title = ""
        if cfg.get("title_attr"):
            title = (link.attributes.get(cfg["title_attr"]) or "").strip()
            if not title:
                title = (node.attributes.get(cfg["title_attr"]) or "").strip()
        if not title:
            tsel = cfg.get("title_sel")
            title = _text(node.css_first(tsel) if tsel else link)
        title = " ".join(title.split())
        if not title:
            continue

        seen.add(url)
        date_node = node.css_first(cfg["date_sel"]) if cfg.get("date_sel") else None
        org_node = node.css_first(cfg["org_sel"]) if cfg.get("org_sel") else None
        items.append({
            "title": title,
            "url": url,
            "publish_date": parse_date_text(_text(date_node)) if date_node else None,
            "org": _text(org_node) or cfg.get("org"),
        })
    return items


def matches_keywords(text: str, keywords) -> bool:
    """任一关键词命中即通过（大小写不敏感）。keywords 为空视为全部通过。"""
    if not keywords:
        return True
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def apply_noise_filters(items: list[dict], cfg: dict,
                        today: date | None = None) -> list[dict]:
    """过滤列表页噪音，避免为无用条目抓详情。

    max_age_days  发布超过该天数的条目丢弃（政务站"归档/须知"栏目常见陈年条目），
                  默认 540 天；填 0 关闭。无发布日期的条目一律保留。
    exclude_url   URL 含任一子串则丢弃（用于排除站内与招聘无关的子栏目）。
    title_keywords 标题或单位含任一关键词才保留。用于栏目混杂、但"是不是招聘稿件"
                  看标题就能判断的源（如韶关人社栏目里大量法院送达公告）。
    """
    max_age = cfg.get("max_age_days", 540)
    if max_age:
        cutoff = ((today or date.today()) - timedelta(days=max_age)).isoformat()
        items = [i for i in items
                 if not i["publish_date"] or i["publish_date"] >= cutoff]
    pats = cfg.get("exclude_url")
    if pats:
        items = [i for i in items if not any(p in i["url"] for p in pats)]
    kw = cfg.get("title_keywords")
    if kw:
        items = [i for i in items if matches_keywords(
            f"{i['title']} {i.get('org') or ''}", kw)]
    return items


def densest_block(tree, min_len: int = 200):
    """挑出正文最可能的容器：文本最多、且链接占比最低的块。

    导航栏/页脚这类块虽然文本量不小，但几乎全是链接，用链接文本量加权压低其得分。
    多家政务站与律协站的正文容器没有稳定的 class，靠这个兜底比取整页 <body> 干净得多。
    """
    best, best_score = None, 0.0
    for n in tree.css("div, article, section, main, td"):
        txt = n.text(separator="\n", strip=True)
        if len(txt) < min_len:
            continue
        link_len = sum(len(a.text(strip=True) or "") for a in n.css("a"))
        score = len(txt) - 2 * link_len
        if score > best_score:
            best, best_score = n, score
    return best


def extract_text(html: str, sel: str | None) -> str:
    tree = HTMLParser(html)
    node = None
    if sel:
        for part in sel.split("|"):
            cand = tree.css_first(part.strip())
            # 命中但内容过少说明选择器指到了壳子（如只剩导航），交给兜底重挑
            if cand is not None and len(cand.text(strip=True)) >= 80:
                node = cand
                break
    if node is None:
        node = densest_block(tree) or tree.body
    return node.text(separator="\n", strip=True) if node else ""


def enrich(item: dict, body: str, cfg: dict) -> dict:
    item["body"] = body
    item["deadline"] = guess_deadline(body)
    item["job_type"] = cfg.get("job_type") or infer_job_type(item["title"])
    # 城市在标题里往往不出现（"2026年公开招聘工作人员公告"），单位名和正文
    # 开头才是它最常出现的地方 —— 三处一起查，实测空值率从 55% 降到 ~25%
    item["city"] = (cfg.get("city")
                    or infer_city(f"{item['title']} {item.get('org') or ''} {body[:300]}"))
    # 职位板/律所招聘栏目里的条目本身就是开放岗位，标题常是"法务助理""某某律师事务所"
    # 这类不含"招聘"字样的短名，靠标题判性质会误判成"其他信息"，所以允许源级指定。
    item["notice_kind"] = cfg.get("notice_kind") or infer_notice_kind(item["title"], body)
    # 用工性质（编制/合同制/派遣）与"长期有效"：从标题+正文推，抽不到就空着
    emp_text = f"{item['title']} {body[:3000]}"
    item["employment_type"] = infer_employment_type(emp_text)
    item["rolling"] = 1 if is_rolling(emp_text) else 0
    # 单位：列表页给了就用列表页的；没有就从标题抽——政务站列表页根本没有单位字段，
    # 但单位名就在标题开头（"广东省高级人民法院…"），抽不到则留空，宁缺勿错。
    if not item.get("org"):
        item["org"] = cfg.get("org") or extract_org(item["title"])
    return item


class Adapter:
    """配置驱动的静态列表适配器。config 字段见 docs/source-registry.md。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        """抓取列表并补全详情。known_fps 为已知 URL 指纹，命中则跳过详情抓取
        （增量采集：日常运行只处理新条目）。"""
        cfg = self.cfg
        known = known_fps or set()
        items, seen = [], set()
        for url in cfg.get("list_urls") or [cfg["list_url"]]:
            r = fetch(url, encoding=cfg.get("encoding"),
                      verify=cfg.get("verify", True))
            for it in parse_list(r.text, {**cfg, "list_url": url}):
                if it["url"] in seen:
                    continue
                seen.add(it["url"])
                items.append(it)
            if len(items) >= cfg.get("max_items", 30):
                break
        items = items[: cfg.get("max_items", 30)]
        items = apply_noise_filters(items, cfg)
        if cfg.get("no_detail"):
            out = [enrich(it, "", cfg) for it in items]
        else:
            todo = [it for it in items if url_fingerprint(it["url"]) not in known]
            bodies = fetch_details(todo, cfg.get("encoding"), cfg.get("verify", True),
                                  cfg.get("detail_sel"),
                                  cfg.get("workers", 6),
                                  cfg.get("detail_budget", 90.0))
            out = [enrich(it, body, cfg) for it, body in zip(todo, bodies)]
        kw = cfg.get("keep_keywords")
        if kw:
            # 取并集语义：列表标题、单位或详情正文任一命中法学关键词即保留
            # （校园职位板标题多是"管培生"之类，法学岗信息只在正文专业要求里）
            out = [x for x in out if matches_keywords(
                f"{x['title']} {x.get('org') or ''} {x.get('body') or ''}", kw)]
        return out


def fetch_details(items: list[dict], encoding, verify: bool, detail_sel,
                  workers: int = 6, budget: float = 90.0,
                  timeout: float = 20.0) -> list[str]:
    """并发抓详情正文，保序返回。单条失败不放弃该条，正文置空继续。

    budget 为该源的墙钟预算（秒）：慢站（如深圳人社）不能拖垮整轮采集，
    超预算后剩余条目只保留列表页已拿到的标题/日期，正文与截止日期留空。
    """
    if not items:
        return []
    results = [""] * len(items)
    deadline = time.monotonic() + budget

    def one(it):
        try:
            d = fetch(it["url"], encoding=encoding, verify=verify,
                      tries=2, timeout=timeout)
            return extract_text(d.text, detail_sel)
        except Exception:  # noqa: BLE001 详情抓取失败不放弃该条
            return ""

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as ex:
        futures = {}
        for i, it in enumerate(items):
            if time.monotonic() >= deadline:
                log.warning("detail budget %.0fs exhausted, %d items left without body",
                            budget, len(items) - i)
                break
            futures[ex.submit(one, it)] = i
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
    return results


def adapter_from_source_row(row) -> Adapter:
    return Adapter(json.loads(row["config"] or "{}"))
