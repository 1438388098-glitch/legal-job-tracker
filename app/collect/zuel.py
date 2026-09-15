import re
from urllib.parse import urljoin

from ..classify import (NOTICE_OPENING, infer_city, infer_employment_type,
                        infer_job_type, is_rolling)
from ..dateparse import parse_date_text
from .http import fetch

# 岗位名里出现这些词，才算"法学岗"。
# 为什么要卡岗位名而不是专业：该接口的 majors 字段会把企业所有接受的专业列全
# （实测"厦门国际银行｜银行"一条列了 38 个专业，含法学），只按 majors 过滤会把
# 银行柜员、供应链、会计专员这类泛岗位全捞进来 —— 正是用户说的"乱七八糟"。
ROLE_KW = [
    "法务", "法律", "律师", "合规", "风控", "知识产权", "专利", "商标",
    "诉讼", "仲裁", "公证", "司法", "检察", "法官", "法规", "合同", "法务顾问",
]
_ROLE = re.compile("|".join(ROLE_KW))


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _legal_positions(pos_text: str) -> str:
    """岗位名是逗号分隔的多岗位串，只留下法学相关的那些。

    "党工团干事,土木/土建/结构工程师,法务专员" → "法务专员"
    这样列表里显示的就是真正可投的那个岗位，而不是一长串无关岗位。
    """
    parts = [p.strip() for p in re.split(r"[,，、;；/|]", pos_text) if p.strip()]
    hits = [p for p in parts if _ROLE.search(p)]
    return "、".join(hits) if hits else ""


def parse_payload(data: dict, base: str) -> list[dict]:
    """把就业中心 JSON 记录映射为统一条目。

    该接口的关键字段（2026-09 实测）：
      title        公告标题（往往就是单位名）
      companyName  单位名
      positionNames 岗位名，逗号分隔
      majors       专业要求，逗号分隔（企业常把 30+ 个专业列全，不能当法学筛选依据）
      education / number / nature / scale  学历 / 人数 / 单位性质 / 规模
      validTime    投递截止   createTime  发布时间
    """
    rows = (data or {}).get("data") or []
    out = []
    for r in rows:
        rid = r.get("id")
        org = _s(r.get("companyName")) or _s(r.get("title"))
        pos_all = _s(r.get("positionNames"))
        # 关键过滤：岗位名里必须有法学相关角色，否则整条丢弃
        pos = _legal_positions(pos_all)
        if not pos:
            continue
        title = f"{org}｜{pos}" if org else pos
        if not title:
            continue
        nature = _s(r.get("nature"))
        body = "\n".join(x for x in [
            f"单位：{org}",
            f"岗位：{pos}",
            f"（该单位本批共招：{pos_all}）" if pos_all and pos_all != pos else "",
            f"单位性质：{nature}",
            f"专业要求：{_s(r.get('majors'))}",
            f"学历要求：{_s(r.get('education'))}",
            f"招聘人数：{_s(r.get('number'))}",
            f"单位规模：{_s(r.get('scale'))}",
            f"宣讲时间：{_s(r.get('holdTime'))}",
            f"宣讲地点：{_s(r.get('holdAddress'))}",
            f"投递截止：{_s(r.get('validTime'))}",
            f"发布时间：{_s(r.get('createTime'))}",
            f"详情页：{urljoin(base, f'/#/home/careerDetail?id={rid}') if rid else ''}",
        ] if x and x.split("：", 1)[-1])
        out.append({
            "title": title,
            "org": org,
            "url": (urljoin(base, f"/#/home/careerDetail?id={rid}") if rid
                    else urljoin(base, "/#/home/career")),
            "deadline": parse_date_text(_s(r.get("validTime"))),
            "publish_date": parse_date_text(_s(r.get("createTime"))),
            "city": infer_city(f"{_s(r.get('holdAddress'))} {_s(r.get('holdSchool'))}"),
            "job_type": infer_job_type(f"{title} {nature}"),
            "notice_kind": NOTICE_OPENING,  # 就业中心职位板上的都是开放岗位
            "employment_type": infer_employment_type(f"{title} {nature} {body}"),
            "rolling": 1 if is_rolling(f"{title} {body}") else 0,
            "body": body,
        })
    return out


class Adapter:
    """中南财经政法大学就业中心 JSON 接口适配器（免登录，已验证）。

    该接口支持 `majors=` 服务端过滤，但语义不完整（majors=法学 仅返回 4 条，
    而按 majors 字段客户端匹配可命中约 1/3 的近期记录），因此这里按页拉取最新记录，
    再用"岗位名必须含法学角色词"在客户端过滤。
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
            payload = r.json()
            # 判"翻到底"要看原始记录数：本页记录被角色过滤清空不代表没有下一页
            if not (payload.get("data") or []):
                break
            out.extend(parse_payload(payload, self.base))
        return out
