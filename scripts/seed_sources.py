"""T1/T2 信息源配置（当前 14 个：13 个静态源 + 中南财 JSON 接口）。

选择器均以 tests/fixtures/<slug>_list.html 真实录制页面逐条校准（2026-09-15）。
校准方法：
    python scripts/probe_sources.py            # 容器候选
    python scripts/peek.py <slug> <正则>        # 原始 HTML 片段
    python scripts/inspect_page.py <文件>       # 结构概览

字段含义见 app/collect/generic_html.py 顶部注释。
"""
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

# 校园招聘站是"全校全专业"职位板，噪音极大，只保留法学相关岗位
LAW_KW = ["法学", "法律", "法务", "律师", "司法", "检察", "法院", "仲裁",
          "合规", "风控", "知识产权", "专利", "公证", "法制", "诉讼"]


def _idx(base: str, n: int) -> list[str]:
    """把 .../index.html 展开为首页 + index_2..index_n（政务 CMS 通用规律）。"""
    stem = base[:-5] if base.endswith(".html") else base
    return [f"{stem}.html"] + [f"{stem}_{i}.html" for i in range(2, n + 1)]


def _q(url: str, param: str, n: int) -> list[str]:
    """?...&page=1..n 型分页。"""
    sep = "&" if "?" in url else "?"
    return [url] + [f"{url}{sep}{param}={i}" for i in range(2, n + 1)]


def _kw(base: str, keywords, param: str = "keyword") -> list[str]:
    """站内关键词检索型入口（高校就业平台支持 ?keyword=，比全量拉取后本地过滤精准）。"""
    return [f"{base}?{param}={quote(k)}" for k in keywords]


# 校园职位板的站内检索词。这些平台详情页是 JS 渲染、拿不到"专业要求"字段，
# 只能靠站内检索把法学相关岗位捞出来；检索结果里偶有泛管理岗（其岗位描述提到法务），
# 属可接受噪音，因此不再叠加本地关键词过滤。
LAW_QUERY = ["法务", "律师", "法律", "合规", "知识产权", "专利"]


def _html(name, urls, item_sel, link_sel="a", title_sel=None, title_attr=None,
          date_sel=None, org_sel=None, detail_sel=None, city=None, job_type=None,
          keep_keywords=None, **extra):
    extra.setdefault("max_items", 30)
    cfg = dict(list_url=urls[0], item_sel=item_sel, link_sel=link_sel, **extra)
    for k, v in (("list_urls", urls if len(urls) > 1 else None), ("title_sel", title_sel),
                 ("title_attr", title_attr), ("date_sel", date_sel), ("org_sel", org_sel),
                 ("detail_sel", detail_sel), ("keep_keywords", keep_keywords)):
        if v:
            cfg[k] = v
    return dict(kind="html", city=city, job_type=job_type, config=cfg, name=name)


SOURCES = [
    # ── 体制内：法院 / 检察院 ───────────────────────────────────────────
    # 分页策略：日常增量采集只需首页（新岗位总在最上面），只有省法院/省人社厅
    # 这类"主源"多翻一页做历史补齐；慢站一律只抓首页，靠 detail_budget 兜底。
    dict(slug="gdcourts", **_html(
        "广东法院网·工作公告",
        _idx("https://www.gdcourts.gov.cn/gsxx/fayuangonggao/index.html", 2),
        "ul.list li", title_attr="title", date_sel="span.time",
        detail_sel="div.article", job_type="public")),
    dict(slug="gd_jcy", **_html(
        "广东省检察院·通知公告",
        ["http://www.gd.jcy.gov.cn/tzgg/"],
        "tr", link_sel='a.b16[href^="./20"]', date_sel="span.h12",
        encoding="gb2312", verify=False, max_items=25, job_type="public")),

    # ── 体制内：人社系统事业单位公开招聘 ───────────────────────────────
    dict(slug="hrss_gd", **_html(
        "广东省人社厅·事业单位招聘公告",
        _idx("https://hrss.gd.gov.cn/zwgk/sydwzp/zpgg/index.html", 3),
        "ul.list li", title_attr="title", date_sel="span.pubDate", job_type="public")),
    dict(slug="hrss_gz", **_html(
        "广州市人社局·事业单位公开招聘",
        _idx("https://rsj.gz.gov.cn/ywzt/rszdgg/sydwgkzp/index.html", 1),
        "ul.infoList li", title_attr="title", date_sel="span.time",
        exclude_url=["sydwzpwsbm"],  # 排除"网上报名"子栏目的报名须知
        max_items=20, detail_budget=60, city="广州", job_type="public")),
    dict(slug="hrss_sz", **_html(
        "深圳市人社局·公职人员招考",
        _idx("http://hrss.sz.gov.cn/gzryzk/index.html", 1),
        "div.AllListCon li", title_attr="title", date_sel="span",
        url_scheme="http",  # 该站 https 在本机 OpenSSL 下握手失败（BAD_ECPOINT）
        max_items=20, detail_budget=60, city="深圳", job_type="public")),
    dict(slug="hrss_zs", **_html(
        "中山市人社局·事业单位公开招聘",
        _idx("http://hrss.zs.gov.cn/xxgk/rsxx/sydwgkzp/index.html", 1),
        "ul.news_list li", date_sel="span",
        max_items=20, city="中山", job_type="public")),
    dict(slug="hrss_zh", **_html(
        "珠海市人社局·公职招考",
        _idx("https://zhrsj.zhuhai.gov.cn/zw/tzgg/gzzk/index.html", 1),
        "ul.news-list-02 li", title_attr="title", date_sel="span.time",
        max_items=20, city="珠海", job_type="public")),
    dict(slug="hrss_fs", **_html(
        "佛山市人社局·机关事业单位招录",
        _idx("https://hrss.foshan.gov.cn/zwgk/jgsydwzl/index.html", 1),
        "div.list_rightbox li", title_attr="title", date_sel="span.time",
        max_items=20, city="佛山", job_type="public")),
    dict(slug="sg_gov", **_html(
        "韶关市人社局·通知公告",
        _idx("https://www.sg.gov.cn/bmpdlm/rlzyhshbzj/tzgg/index.html", 1),
        "div.pageList ul li", title_attr="title", date_sel="span.time",
        # 该栏目夹杂大量"送达公告/退休公示"，只保留人事招聘类稿件
        title_keywords=["招聘", "招录", "考录", "选聘", "选调", "引进", "岗位",
                        "拟聘", "聘用", "雇员", "招募", "面试", "笔试", "英才"],
        city="韶关", job_type="public")),

    # ── 律所 / 律师行业 ────────────────────────────────────────────────
    dict(slug="fs_lvxie", **_html(
        "广东律师网·律所招聘",
        _q("https://www.gdlawyers.net/recruit/index.html", "page", 2),
        'div.recruit.ny a[href*="recruit/details"]', link_sel="self",
        title_attr="title", detail_sel="div.page-right", job_type="lawfirm",
        notice_kind="opening")),
    dict(slug="hz_lvxie", **_html(
        "惠州市律协·律所招聘",
        _q("https://new.hzlawyers.cn/list/recruitment_info", "page", 1),
        'a[href^="/show/"]', link_sel="self", title_sel="div.text-base",
        date_sel="div.text-xs div", detail_sel="div.rich-text",
        max_items=20, city="惠州", job_type="lawfirm", notice_kind="opening")),

    # ── 高校就业网（站内关键词检索法学岗）────────────────────────────
    # 该平台详情页为 JS 渲染，HTML 里拿不到"专业要求"，但站内 ?keyword= 检索可用，
    # 用法学检索词直接取岗位（实测"法务"→法务专员/法务助理，"律师"→律师助理/仲裁院书记员）。
    dict(slug="gdufs", **_html(
        "广东外语外贸大学·招聘职位",
        _kw("https://career.gdufs.edu.cn/index.php/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, notice_kind="opening")),
    dict(slug="gzhu", **_html(
        "广州大学·职位信息",
        _kw("https://jy.gzhu.edu.cn/index.php/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, notice_kind="opening")),

    # ── 外校就业中心 JSON 接口（免登录，已验证）────────────────────────
    dict(slug="zuel", name="中南财经政法大学·就业中心", kind="zuel", city=None,
         job_type=None, config=dict(
             api="https://jyzx.zuel.edu.cn/api/publicly/recruit/list",
             base="https://jyzx.zuel.edu.cn", type=1, pages=4, limit=20,
             keep_keywords=LAW_KW)),
]


def main(db_path="data/job.db"):
    conn = db.connect(db_path)
    db.init_db(conn)
    for s in SOURCES:
        conn.execute(
            "INSERT INTO sources(slug,name,kind,city,job_type,config) "
            "VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
            "city=excluded.city, job_type=excluded.job_type, config=excluded.config",
            (s["slug"], s["name"], s["kind"], s.get("city"), s.get("job_type"),
             json.dumps(s["config"], ensure_ascii=False)))
    conn.commit()
    print(f"seeded {len(SOURCES)} sources -> {db_path}")


if __name__ == "__main__":
    main(*sys.argv[1:])
