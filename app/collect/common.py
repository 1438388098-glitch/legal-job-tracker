"""采集适配器共用的字段构建逻辑。

曾经五个适配器（generic_html / zuel / ggfw / hotjob / swupl）各写一遍
"标题+单位+正文 → 岗位类型/城市/截止日/用工性质"的映射，代价是**逻辑静默漂移**：
- swupl 忘了调 infer_employment_type，该源用工性质恒为空；
- reclassify.py 抄了一份但截止日改成"无条件覆盖"，重算一次就把深圳律协
  列表页直接给出的准确截止日（`deadline_sel`）冲掉了。

所以收敛为这一个 `finalize()`：**采集时和重算时走同一条代码路径**，
规则改一次就到处生效，不会再漂。

用法（各适配器）：
    item = finalize({"title": t, "url": u, "org": o}, body, cfg)
"""


def s(value) -> str:
    """None → '' 并去空白。各适配器原本各复制一份。"""
    return (value or "").strip()


def matches_keywords(text: str, keywords) -> bool:
    """任一关键词命中即通过（大小写不敏感）。keywords 为空视为全部通过。"""
    if not keywords:
        return True
    t = (text or "").lower()
    return any(str(k).lower() in t for k in keywords)


def apply_keep_keywords(items: list[dict], keywords) -> list[dict]:
    """按"标题+单位+正文"过滤条目。关键词为空则原样返回。"""
    if not keywords:
        return items
    return [x for x in items if matches_keywords(
        f"{x.get('title') or ''} {x.get('org') or ''} {x.get('body') or ''}", keywords)]


def finalize(item: dict, body: str, cfg: dict | None = None) -> dict:
    """把"标题/单位/正文"补全成一条可入库的岗位记录。

    cfg 是源级配置（city / job_type / notice_kind / org 等固有属性）。
    **不要**在这里写任何针对单个源的特例——特例放 cfg 里。
    """
    from ..classify import (extract_org, infer_city, infer_employment_type,
                            infer_job_type, infer_notice_kind, is_rolling)
    from ..dateparse import guess_deadline

    cfg = cfg or {}
    item["body"] = body or ""

    # 正文推断出的截止日优先；列表页直接给的（如深圳律协的截止日列）作兜底。
    # 顺序不能反——列表页的 deadline_sel 只在正文抽不到时才用。
    item["deadline"] = guess_deadline(body) or item.get("deadline") or None

    title = item.get("title") or ""
    # 单位名一起看：标题常是"招聘公告"这种中性措辞，真正的类型线索在单位名里
    # （"XX律师事务所…招聘公告"），只看标题会大量落进"其他"
    item["job_type"] = cfg.get("job_type") or infer_job_type(
        f"{title} {item.get('org') or ''}")

    # 城市在标题里常常不出现（"2026年公开招聘工作人员公告"），单位名和正文
    # 开头才是它最常出现的地方 —— 三处一起查，实测空值率从 55% 降到 ~25%
    if not item.get("city"):
        item["city"] = cfg.get("city") or infer_city(
            f"{title} {item.get('org') or ''} {(body or '')[:300]}")

    # 职位板/律所招聘栏目里的条目本身就是开放岗位，标题常是"法务助理"这类不含
    # "招聘"字样的短名，靠标题判性质会误判成"其他信息"，所以允许源级指定。
    item["notice_kind"] = cfg.get("notice_kind") or infer_notice_kind(title, body)

    # 用工性质（编制/合同制/派遣）与"长期有效"
    emp_text = f"{title} {(body or '')[:3000]}"
    if not item.get("employment_type"):
        item["employment_type"] = infer_employment_type(emp_text)
    item["rolling"] = 1 if item.get("rolling") else (1 if is_rolling(emp_text) else 0)

    # 单位：列表页给了就用列表页的；没有就从标题抽——政务站列表页根本没有单位
    # 字段，但单位名就在标题开头（"广东省高级人民法院…"），抽不到留空，宁缺勿错。
    if not item.get("org"):
        item["org"] = cfg.get("org") or extract_org(title)

    return item
