"""高校就业网「frontpage + f/ajaxHome」平台适配器。

一批高校的就业网用的是同一套模板（jQuery + artTemplate，JS 路径形如
`/frontpage/<学校代号>/js/index.js`），首页列表走同一个接口：

    GET {base}/f/ajaxHome/ajax_findRecruitmentinfoLimitList?num=30&positionType=1
    Referer: {base}/

已知站点：北京大学 scc.pku.edu.cn、武汉大学 xsjy.whu.edu.cn。
北大模板的 init.js 里还硬编码了其他学校的路径（cuc 中国传媒大学等），
说明这套接口服务多所高校——换 base 就能接新学校，无需重新逆向。

接口的两个硬限制（实测）：
- **分页无效**：`page=2` / `pageNum=2` 返回条数不变，`num` 也有天花板（北大 6~9 条，
  武大 9~10 条）。所以只能当"最新 N 条"的增量源，不能用来翻历史。
- **服务端检索无效**：`keyword=法务` 不缩小结果集 → 法学岗过滤只能在本地做。

数据质量差异（设计时按最差情况处理）：
- 武大 `corporationinfo.name` 是真实单位名，北大返回的是"北京大学学生就业指导服务中心"
  这类学校自己的名字。所以单位名要判断：像学校就业中心就直接从标题里抽。
"""
import logging
from urllib.parse import urljoin

from ..classify import extract_org
from ..dateparse import parse_date_text
from .common import apply_keep_keywords, finalize
from .http import fetch

log = logging.getLogger("collect.frontpage")

# 北大等校把 corporationinfo.name 填成了学校自己的就业中心，不能当单位名
_NOT_ORG = ("就业指导", "就业服务", "学生就业", "就业中心", "职业发展", "career")


def parse_payload(payload: dict, base: str) -> list[dict]:
    objs = payload.get("object") or payload.get("rows") or []
    out = []
    for o in objs:
        title = (o.get("title") or "").strip()
        if not title:
            continue
        corp = (o.get("corporationinfo") or {})
        name = (corp.get("name") or "").strip()
        if not name or any(k in name for k in _NOT_ORG):
            name = extract_org(title)
        jid = o.get("id") or ""
        url = o.get("detailsUrl") or o.get("linkUrl") or o.get("url") or (
            f"{base}/f/recruitmentinfo/show?recruitmentId={jid}")
        if not str(url).startswith("http"):
            url = urljoin(base + "/", str(url))
        body_parts = []
        for pos in (o.get("recruitmentPositionList") or []):
            if isinstance(pos, dict):
                body_parts.append(str(pos.get("name") or pos.get("positionName") or ""))
        body = " ".join(x for x in body_parts if x)
        out.append({
            "title": title,
            "url": url,
            "org": name or None,
            # startTime 是发布时间，endTime 是投递截止——接口直接给，比正文猜可靠
            "publish_date": parse_date_text(str(o.get("startTime") or "")),
            "deadline": parse_date_text(str(o.get("endTime") or "")),
            "city": (o.get("cityName") or "").strip() or None,
            "body": body,
            "_major": (o.get("majorName") or "").strip(),
            "_edu": (o.get("education") or "").strip(),
        })
    return out


class Adapter:

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.base = cfg.get("base", "")
        self.api = cfg.get("api") or f"{self.base}/f/ajaxHome/ajax_findRecruitmentinfoLimitList"
        self.num = int(cfg.get("num", 30))
        self.pos_types = cfg.get("position_types") or [1]

    def collect(self, known_fps: set[str] | None = None) -> list[dict]:
        out: list[dict] = []
        errors: list[str] = []
        seen: set[str] = set()
        for pt in self.pos_types:
            try:
                d = fetch(self.api, params={"num": self.num, "positionType": pt},
                          headers={"Referer": self.base + "/"}).json()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type(e).__name__}: {e}")
                log.warning("frontpage %s positionType=%s 失败：%s", self.base, pt, e)
                continue
            for it in parse_payload(d, self.base):
                if it["url"] in seen:
                    continue
                seen.add(it["url"])
                out.append(it)
        if not out and errors:
            raise RuntimeError(f"接口全部失败：{errors[0][:180]}")
        # 考研/就业政策类公告也会出现在这个接口里，按关键词滤掉非岗位
        out = apply_keep_keywords(out, self.cfg.get("keep_keywords"))
        return [finalize(x, x.pop("body", ""), self.cfg) for x in out]
