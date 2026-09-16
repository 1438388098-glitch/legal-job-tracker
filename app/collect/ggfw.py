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
import logging
from urllib.parse import urljoin

from ..classify import (LAW_KEYWORDS, infer_city, infer_employment_type,
                        infer_job_type, is_rolling)
from ..dateparse import parse_date_text
from .common import apply_keep_keywords, matches_keywords, s as _s

log = logging.getLogger("collect.ggfw")
from .http import post_json

DEFAULT_KEYWORDS = list(LAW_KEYWORDS)   # 单一真源：app.classify


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
        errors: list[str] = []
        for kw in self.keywords:
            for page in range(1, self.pages + 1):
                try:
                    d = post_json(
                        self.api,
                        json_body={"pageTag": "01", "current": page, "size": self.size,
                                   "aab020": self.unit_kinds, "bce055": kw},
                        headers={"Referer": self.referer})
                except Exception as e:  # noqa: BLE001 接口偶发抽风，跳过该关键词剩余页
                    errors.append(f"{kw}#p{page}: {type(e).__name__}: {e}")
                    log.warning("ggfw %s 第 %s 页失败：%s", kw, page, e)
                    break
                items = parse_payload(d, self.base)   # parse_payload 吃完整响应
                if not items:
                    break
                out.extend(items)
                data = d.get("data") or {}
                if page >= int(data.get("pages") or 1):
                    break
        out = apply_keep_keywords(out, self.cfg.get("keep_keywords"))
        # 一个关键词都没拿到且次次报错 = 接口挂了。必须抛出去让 runner 记进源健康，
        # 否则返回空列表会被当成"这次没新岗位"，源健康页一直显示绿灯。
        if not out and errors and len(errors) >= len(self.keywords):
            raise RuntimeError(f"接口全部失败（{len(errors)}/{len(self.keywords)} 个关键词）："
                               f"{errors[0][:160]}")
        return out
