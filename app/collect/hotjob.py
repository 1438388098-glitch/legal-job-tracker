"""大易（hotjob.cn）招聘系统适配器 —— 以越秀集团为首个接入方。

大量国企集团官网用大易系统做招聘（页面是 Vue 模板，纯 JS 渲染，静态抓不到），
但它有一个稳定的 JSON 接口：

    GET https://yuexiu.hotjob.cn/wt/YUEXIU/web/json/position/list
        ?brandCode=1&recruitPostType=1&pageNo=1&pageSize=20

列表响应里就带 workContent（工作内容）和 serviceCondition（任职要求），
不需要再抓详情页；详情页 `/web/jobDetail?postId=N` 是 JS 壳。
以后遇到其他用 hotjob.cn 的集团，改 cfg 里的 api/detail_base 就能复用。
"""
import logging
from urllib.parse import urljoin

from ..classify import (infer_city, infer_employment_type, infer_job_type,
                        is_rolling)
from ..dateparse import parse_date_text
from .common import apply_keep_keywords, matches_keywords, s as _s
from .http import fetch

log = logging.getLogger("collect.hotjob")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def parse_payload(data: dict, detail_base: str) -> list[dict]:
    out = []
    for p in data.get("postList") or []:
        pid = _s(p.get("postId"))
        if not pid:
            continue
        org = _s(p.get("orgName")) or _s(p.get("deptOrgName"))
        pos = _s(p.get("postName"))
        title = f"{org}｜{pos}" if org else pos
        if not title:
            continue
        body = "\n".join(x for x in [
            f"单位：{org}",
            f"部门：{_s(p.get('deptOrgName'))}",
            f"岗位：{pos}",
            f"招聘人数：{_s(p.get('recruitNum'))}",
            f"工作地点：{_s(p.get('workPlace'))}",
            f"招聘类型：{_s(p.get('recruitType'))}",
            f"工作内容：{_s(p.get('workContent'))[:800]}",
            f"任职要求：{_s(p.get('serviceCondition'))[:800]}",
            f"发布日期：{_s(p.get('publishDate'))}",
            f"截止日期：{_s(p.get('endDate'))}",
        ] if x.split("：", 1)[-1])
        text = f"{title} {body}"
        out.append({
            "title": title,
            "org": org or None,
            "url": urljoin(detail_base, f"?postId={pid}") if detail_base else f"?postId={pid}",
            "publish_date": parse_date_text(_s(p.get("publishDate"))),
            # 大易列表直接给 endDate，比从正文猜可靠
            "deadline": parse_date_text(_s(p.get("endDate"))),
            "city": infer_city(f"{_s(p.get('workPlace'))} {org}"),
            "job_type": infer_job_type(text),
            "notice_kind": "opening",
            "employment_type": infer_employment_type(text),
            "rolling": 1 if (p.get("isLongTermRelease") or is_rolling(text)) else 0,
            "body": body,
        })
    return out


class Adapter:
    """大易系统岗位列表。keep_keywords 用于只留法学相关岗（集团岗位以技术为主）。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api = cfg["api"]
        self.detail_base = cfg.get("detail_base", "")
        self.brand_code = cfg.get("brand_code", 1)
        self.post_type = cfg.get("post_type", 1)      # 1=社招（校招另有通道）
        self.pages = int(cfg.get("pages", 5))
        self.limit = int(cfg.get("limit", 50))

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        out = []
        # positionName 是服务端精准过滤（实测"法务"把 519 条收敛到 7 条），
        # 比全量翻 52 页再本地过滤省一个数量级的请求
        kws = self.cfg.get("position_keywords") or [None]
        errors: list[str] = []
        for kw in kws:
            for page in range(1, self.pages + 1):
                params = {"brandCode": self.brand_code, "recruitPostType": self.post_type,
                          "pageNo": page, "pageSize": self.limit}
                if kw:
                    params["positionName"] = kw
                try:
                    d = fetch(self.api, params=params).json()
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{kw}#p{page}: {type(e).__name__}: {e}")
                    log.warning("hotjob %s 第 %s 页失败：%s", kw, page, e)
                    break
                items = parse_payload(d, self.detail_base)
                if not items:
                    break
                out.extend(items)
                if page >= int(d.get("pageCount") or 1):
                    break
        out = apply_keep_keywords(out, self.cfg.get("keep_keywords"))
        # 同 ggfw：接口全挂必须抛出去，否则源健康页会一直显示绿灯
        if not out and errors and len(errors) >= len(kws):
            raise RuntimeError(f"接口全部失败（{len(errors)}/{len(kws)} 个关键词）："
                               f"{errors[0][:160]}")
        return out
