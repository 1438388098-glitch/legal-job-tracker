"""西南政法大学就业网（cqbys 平台）适配器。

首页"最新职位"块是服务端渲染（详情页 /job/view/id/N 也是 SSR），但列表搜索页
/job/search 是 JS 渲染抓不到，所以只抓首页增量块。条目形态特殊：

    <li><time>09-15</time>
      <h3><a href="/company/view/id/N">单位名</a></h3>
      <p><a href="/job/view/id/N">岗位1</a>,<a>岗位2</a></p></li>

一条记录是"一个单位 + 多个岗位"，这里拆成"每岗位一条"，单位从 h3 取——
五院四系的单位多为律所/法检，拆开更符合求职者的浏览方式。
"""
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..dateparse import parse_date_text
from .common import apply_keep_keywords, finalize, s as _s
from .http import fetch


def parse_list(html: str, base: str, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or {}
    tree = HTMLParser(html)
    out = []
    for li in tree.css(cfg.get("item_sel", "div.newslist ul li")):
        org = ""
        h3a = li.css_first("h3 a")
        if h3a is not None:
            org = h3a.text(strip=True)
        date_node = li.css_first("time")
        date = parse_date_text(_s(date_node.text(strip=True)) if date_node else "")
        for a in li.css("p a[href]"):
            pos = _s(a.text(strip=True))
            href = a.attributes.get("href") or ""
            if not pos or "/job/view/" not in href:
                continue
            title = f"{org}｜{pos}" if org else pos
            # 走通用 finalize：此前这里手写字段，漏掉了用工性质/长期有效的推断
            out.append(finalize({
                "title": title,
                "org": org or None,
                "url": urljoin(base, href),
                "publish_date": date,
                "deadline": None,
            }, "", cfg))
    return out


class Adapter:

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.list_url = cfg.get("list_url", "https://swupl.cqbys.com/")
        self.item_sel = cfg.get("item_sel", "div.newslist ul li")

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        r = fetch(self.list_url, encoding=self.cfg.get("encoding"),
                  verify=self.cfg.get("verify", True))
        items = parse_list(r.text, self.list_url,
                           {k: v for k, v in self.cfg.items()
                            if k in ("item_sel", "job_type", "notice_kind")})
        kw = self.cfg.get("keep_keywords")
        if kw:
            items = apply_keep_keywords(items, kw)
        return items
