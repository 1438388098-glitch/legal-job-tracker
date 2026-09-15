"""广东省人社厅公共就业服务平台的"国企招聘专区"适配器。

这是全省国企岗位覆盖的主干源：政策要求国企招聘信息公开，该平台聚合了
省属/市属国企（含二级公司）的实时岗位流。接口是从前端 chunk 逆向出来的：

    POST .../retrieval/c/recruitment/homepage/positions
    body: {"pageTag":"01","current":1,"size":50,
           "aab020":"110,141,151",      # 单位性质=国有/国有控股（不过滤会混入配送员等）
           "bce055":"法务"}             # 岗位名关键词

必须带 Referer（页面同源），否则返回空数据。total 在 500~1000 处封顶，
所以按关键词分片拉取，不按城市分片（城市从 acb204Name 字段推断）。
详情页是 hash 路由的 SPA，静态抓不到正文，条目数据全部来自列表接口。
"""
from urllib.parse import urljoin

from ..classify import (infer_city, infer_employment_type, infer_job_type,
                        is_rolling)
from ..dateparse import parse_date_text
from .generic_html import matches_keywords
from .http import post_json

DEFAULT_KEYWORDS = ["法务", "法律", "法学", "合规", "知识产权", "风控"]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def parse_payload(data: dict, base: str) -> list[dict]:
    """把接口记录映射为统一条目（字段为社保编码体系，2026-09 实测）。"""
    rows = (data or {}).get("data", {}).get("records") or []
    out = []
    for r in rows:
        org = _s(r.get("aab004"))
        pos = _s(r.get("bce055")).rstrip(".、 ")
        if not pos:
            continue
        title = f"{org}｜{pos}" if org else pos
        jid = _s(r.get("bcb009"))
        url = urljoin(base, f"#/jobDetail?bcb009={jid}") if jid else base
        body = "\n".join(x for x in [
            f"单位：{org}",
            f"岗位：{pos}",
            f"薪资：{_s(r.get('bcca68'))}",
            f"地区：{_s(r.get('acb204Name'))}",
            f"招聘类型：{_s(r.get('acb239Name'))}",      # 校招 / 社招
            f"学历要求：{_s(r.get('aac011Name'))}",
            f"发布时间：{_s(r.get('bdb286'))}",
        ] if x.split("：", 1)[-1])
        out.append({
            "title": title,
            "org": org or None,
            "url": url,
            "publish_date": parse_date_text(_s(r.get("bdb286"))[:10]),
            "deadline": None,               # 接口不提供截止日
            "city": infer_city(f"{_s(r.get('acb204Name'))} {org}"),
            "job_type": infer_job_type(f"{title} {body}"),
            "notice_kind": "opening",
            "employment_type": infer_employment_type(f"{title} {body}"),
            "rolling": 1 if is_rolling(f"{title} {body}") else 0,
            "body": body,
        })
    return out


class Adapter:
    """按关键词分片拉取国企岗位；同一岗位命中多个关键词时靠 URL 指纹去重。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api = cfg.get("api", (
            "https://ggfw.hrss.gd.gov.cn/recruitment/internet/main/internet"
            "/retrieval/c/recruitment/homepage/positions"))
        self.base = cfg.get("base", "https://ggfw.hrss.gd.gov.cn/recruitment/internet/main/")
        self.referer = cfg.get("referer", "https://ggfw.hrss.gd.gov.cn/recruitment/internet/main/")
        self.keywords = cfg.get("keywords") or DEFAULT_KEYWORDS
        self.pages = int(cfg.get("pages", 3))
        self.size = int(cfg.get("size", 50))
        self.unit_kinds = cfg.get("unit_kinds", "110,141,151")   # 国企单位性质码

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        out = []
        for kw in self.keywords:
            for page in range(1, self.pages + 1):
                try:
                    d = post_json(
                        self.api,
                        json_body={"pageTag": "01", "current": page, "size": self.size,
                                   "aab020": self.unit_kinds, "bce055": kw},
                        headers={"Referer": self.referer})
                except Exception:  # noqa: BLE001 接口偶发抽风，跳过该关键词剩余页
                    break
                items = parse_payload(d, self.base)   # parse_payload 吃完整响应
                if not items:
                    break
                out.extend(items)
                data = d.get("data") or {}
                if page >= int(data.get("pages") or 1):
                    break
        kw = self.cfg.get("keep_keywords")
        if kw:
            out = [x for x in out if matches_keywords(
                f"{x['title']} {x.get('org') or ''} {x.get('body') or ''}", kw)]
        return out
