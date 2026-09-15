import json
from urllib.parse import urljoin

from ..classify import NOTICE_OPENING, infer_city, infer_job_type
from ..dateparse import parse_date_text
from .http import fetch


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def parse_payload(data: dict, base: str) -> list[dict]:
    """把就业中心 JSON 记录映射为统一条目。

    该接口的关键字段（2026-09 实测）：
      title        公告标题（往往就是单位名）
      companyName  单位名
      positionNames 岗位名
      majors       专业要求，逗号分隔（含"法学"即符合），这是法学筛选的主要依据
      education / number / nature / scale  学历 / 人数 / 单位性质 / 规模
      validTime    投递截止   createTime  发布时间
    """
    rows = (data or {}).get("data") or []
    out = []
    for r in rows:
        rid = r.get("id")
        org = _s(r.get("companyName")) or _s(r.get("title"))
        pos = _s(r.get("positionNames"))
        title = f"{org}｜{pos}" if org and pos and pos not in org else (org or pos)
        if not title:
            continue
        body = "\n".join(x for x in [
            f"单位：{org}",
            f"岗位：{pos}",
            f"专业要求：{_s(r.get('majors'))}",
            f"学历要求：{_s(r.get('education'))}",
            f"招聘人数：{_s(r.get('number'))}",
            f"单位性质：{_s(r.get('nature'))}",
            f"单位规模：{_s(r.get('scale'))}",
            f"宣讲时间：{_s(r.get('holdTime'))}",
            f"宣讲地点：{_s(r.get('holdAddress'))}",
            f"投递截止：{_s(r.get('validTime'))}",
            f"发布时间：{_s(r.get('createTime'))}",
            f"详情页：{urljoin(base, f'/#/home/careerDetail?id={rid}') if rid else ''}",
        ] if x.split("：", 1)[-1])
        out.append({
            "title": title,
            "org": org,
            "url": (urljoin(base, f"/#/home/careerDetail?id={rid}") if rid
                    else urljoin(base, "/#/home/career")),
            "deadline": parse_date_text(_s(r.get("validTime"))),
            "publish_date": parse_date_text(_s(r.get("createTime"))),
            "city": infer_city(f"{_s(r.get('holdAddress'))} {_s(r.get('holdSchool'))}"),
            "job_type": infer_job_type(f"{title} {pos}"),
            "notice_kind": NOTICE_OPENING,  # 就业中心职位板上的都是开放岗位
            "body": body,
        })
    return out


class Adapter:
    """中南财经政法大学就业中心 JSON 接口适配器（免登录，已验证）。

    该接口支持 `majors=` 服务端过滤，但语义不完整（majors=法学 仅返回 4 条，
    而按 majors 字段客户端匹配可命中约 1/3 的近期记录），因此这里仍按页拉取
    最新记录后在客户端按 keep_keywords 过滤，保证召回。
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api = cfg.get("api", "https://jyzx.zuel.edu.cn/api/publicly/recruit/list")
        self.base = cfg.get("base", "https://jyzx.zuel.edu.cn")
        self.rtype = cfg.get("type", 1)
        self.pages = int(cfg.get("pages", 3))
        self.limit = int(cfg.get("limit", 20))

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        out = []
        for page in range(1, self.pages + 1):
            r = fetch(self.api, params={"page": page, "limit": self.limit,
                                        "type": self.rtype})
            items = parse_payload(r.json(), self.base)
            if not items:
                break
            out.extend(items)
        kw = self.cfg.get("keep_keywords")
        if kw:
            from .generic_html import matches_keywords
            out = [x for x in out if matches_keywords(
                f"{x['title']} {x.get('org') or ''} {x.get('body') or ''}", kw)]
        return out
