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
from app.classify import LAW_KEYWORDS, LAW_QUERIES, SOURCE_CATEGORIES  # noqa: E402

# 校园招聘站是"全校全专业"职位板，噪音极大，只保留法学相关岗位。
# 词表统一取自 app.classify（单一真源），这里只做别名，不再各自维护一份
LAW_KW = LAW_KEYWORDS


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
LAW_QUERY = LAW_QUERIES


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
    # 注意：www.gdlawyers.net 实测是"佛山市律师协会"官网（页脚有主办单位声明），
    # 不是省律协；它就是我们最早的律所招聘源。
    dict(slug="fs_lvxie", **_html(
        "佛山市律师协会·律所招聘",
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
    # 广州律协：列表是 JSP 片段接口（GET 即可，无需 POST），职位/律所/日期三列齐全；
    # 详情页正文是 JS 注入抓不到，走 no_detail
    dict(slug="gz_lvxie", **_html(
        "广州市律协·律所招聘",
        _q("https://www.gzlawyer.org/plugins/getIndexZhaopinListCatalog_new.jsp"
           "?lawfirm=&categoryId=", "page", 1),
        "tr", link_sel='a[href^="/lawfirmhr?id="]',
        title_sel="td:nth-child(1)", org_sel="td:nth-child(2)",
        date_sel="td:nth-child(3)",
        no_detail=True, max_items=30, city="广州", job_type="lawfirm",
        notice_kind="opening")),
    # 深圳律协：catalog 页是 SSR 表格，tbody 前两行是登录弹窗的表格（无链接，
    # parse_list 会因取不到链接自动跳过）；列表直接给出截止日列
    dict(slug="sz_lvxie", **_html(
        "深圳市律协·律所招聘",
        _q("https://www.szlawyers.com/catalog/66982c75d70240108a39a1ea57c4c4e5",
           "currentPageNo", 1),
        "tbody tr", link_sel='a[href*="/info/"]',
        title_sel="td:nth-child(2)", org_sel="td:nth-child(1)",
        date_sel="td:nth-child(3)", deadline_sel="td:nth-child(4)",
        no_detail=True, max_items=40, city="深圳", job_type="lawfirm",
        notice_kind="opening")),
    # 中山律协：日期拆在两个节点（"2026-09" + "04"），dateparse 已做归一化，
    # date_sel 直接取包含两个节点的父容器
    dict(slug="zs_lvxie", **_html(
        "中山市律协·律所招聘",
        _q("http://www.gdzslx.com/index.php?c=category&id=25", "page", 1),
        "div.g-list1 ul li", link_sel="a", title_sel="div.tit",
        date_sel="div.date", detail_sel="div.news-cont",
        max_items=20, city="中山", job_type="lawfirm", notice_kind="opening")),
    # 江门律协：list_url 必须带尾斜杠（条目 href 是 ./202609/xxx.html 的相对路径）
    dict(slug="jm_lvxie", **_html(
        "江门市律协·律所招聘",
        ["http://www.jmlawyer.org.cn/xhzx/zpxx/"],
        "div.newslist ul li", link_sel="a", date_sel="span",
        max_items=25, city="江门", job_type="lawfirm", notice_kind="opening")),

    # ── 国企（聚合专栏优先：政策要求国企招聘信息公开，专栏一个源覆盖几十家
    #    一级集团及其二级公司；抽查 9 家集团官网，4 家不可达、4 家 JS 渲染，
    #    逐家攻官网在工程上不成立）────────────────────────────────────────
    dict(slug="gzw_gd", **_html(
        "广东省国资委·百万英才汇南粤（国企招聘）",
        _idx("https://gzw.gd.gov.cn/214/index.html", 2),
        "ul.list li", title_attr="title", date_sel="span",
        detail_sel="div.article|div.content|div.TRS_Editor",
        job_type="public", notice_kind="opening")),
    dict(slug="geg", **_html(
        "广东能源集团·招聘信息",
        _idx("https://www.geg.com.cn/gdyd/zjyd/zhaopin/index.html", 1),
        "ul.news-list li", link_sel="h3 a", date_sel="div.time",
        # 集团岗位以技术类为主，只留法学相关，避免灌入大量无关条目
        keep_keywords=LAW_KW,
        job_type="public", notice_kind="opening")),

    # ── 公务员 / 选调 / 军队文职 ───────────────────────────────────────
    dict(slug="gdzz_luqu", **_html(
        "广东组织工作网·公务员录用",
        _idx("https://www.gdzz.gov.cn/gwygz/lypytzgg/index.html", 2),
        "li.clearfix", link_sel="a", title_attr="title", date_sel="div.time",
        detail_sel="div.zw|div.article|div.content",
        # 栏目里混着各地招录工作新闻稿，只留公告类
        title_keywords=["公告", "录用", "选调", "考试录用", "资格审核", "面试",
                        "报名", "招录"],
        job_type="public", notice_kind="opening")),
    dict(slug="army_81rc", **_html(
        "军队人才网·文职招考公告",
        ["http://81rc.81.cn/sy/tzgg_210284/index.html"],
        "div.left-news li", title_attr="title", date_sel="span",
        detail_sel="#c_center|div.wzzzy_left",
        job_type="public", notice_kind="opening")),

    # ── 人社系统补缺（东莞/韶关人事人才栏）────────────────────────────
    dict(slug="hrss_dg", **_html(
        "东莞市人社局·公开招聘",
        _idx("https://dghrss.dg.gov.cn/xwzx/gsgg/gkzp/index.html", 2),
        "div.infolist.ymd ul li", link_sel="a", date_sel="span",
        city="东莞", job_type="public")),
    # 韶关：人事人才栏比现有 tzgg（大量送达公告）更聚焦，两个源并存
    dict(slug="sg_rsrc", **_html(
        "韶关市人社局·人事人才",
        _idx("https://www.sg.gov.cn/bmpdlm/rlzyhshbzj/yw/rsrc/index.html", 2),
        "div.pageList ul li", title_attr="title", date_sel="span.time",
        title_keywords=["招聘", "招录", "考录", "选聘", "选调", "引进", "岗位",
                        "拟聘", "聘用", "雇员", "招募", "面试", "笔试", "英才"],
        city="韶关", job_type="public")),

    # ── 高校就业网（站内关键词检索法学岗）────────────────────────────
    # 该平台详情页为 JS 渲染、HTML 里拿不到"专业要求"，但站内 ?keyword= 检索可用。
    # 实测站内检索是模糊匹配（搜"法务"会带出会计专员、销售订单管理），
    # 所以再叠一层本地过滤：标题或单位名必须含法学词。
    dict(slug="gdufs", **_html(
        "广东外语外贸大学·招聘职位",
        _kw("https://career.gdufs.edu.cn/index.php/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, keep_keywords=LAW_KW,
        notice_kind="opening")),
    dict(slug="gzhu", **_html(
        "广州大学·职位信息",
        _kw("https://jy.gzhu.edu.cn/index.php/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, keep_keywords=LAW_KW,
        notice_kind="opening")),
    # 广东金融学院 / 广州商学院：与广外/广大同一套平台（A 系），配置照抄换域名
    dict(slug="gduf", **_html(
        "广东金融学院·招聘职位",
        _kw("https://jy.gduf.edu.cn/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, keep_keywords=LAW_KW,
        notice_kind="opening")),
    dict(slug="gcc", **_html(
        "广州商学院·招聘职位",
        _kw("https://jy.gcc.edu.cn/web/Index/job-list", LAW_QUERY),
        "div.jobs-list div.col-xs-6", link_sel="a.job-block",
        title_sel="div.job-name", date_sel="div.job-time", org_sel="div.job-company",
        no_detail=True, max_items=60, keep_keywords=LAW_KW,
        notice_kind="opening")),

    # ── 五院四系：可静态抓的 2 所 ──────────────────────────────────────
    # 清华：唯一"静态 + 真分页(?pgno=) + 服务端岗位名检索(?zwmc=)"三全的高校源。
    # 两个坑：① href 是 javascript:void(0)，真地址在同名自定义属性 ahref；
    #        ② 锚文本是"岗位————单位"，用 title_split 拆开。
    dict(slug="tsinghua", **_html(
        "清华大学·招聘职位",
        _kw("http://career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony/xxfb",
            LAW_QUERY, "zwmc"),
        "ul#todayList li.clearfix", link_sel="a", link_attr="ahref",
        title_attr="title", date_sel="span", title_split="————",
        max_items=60, notice_kind="opening")),
    # 西北政法：法学岗占比最高（实测 10 条里 4 条是法学岗），日更。
    # 限制：只有首页块是服务端渲染（/campus /job/search 等列表页是 JS 渲染），
    # 所以固定 10 条增量；证书链有问题，必须 verify=False。
    dict(slug="nwupl", **_html(
        "西北政法大学·最新职位",
        ["https://job.nwupl.edu.cn/"],
        "ul.css-con7 li.clearfix", link_sel="a.title",
        date_sel="div.new-time", detail_sel="div.news-con|div.article|div.content",
        verify=False, max_items=20, notice_kind="opening")),

    # ── 五院四系：同一套 frontpage 平台的 2 所（JSON 接口）──────────────
    # 北大/武大共用 `f/ajaxHome/ajax_findRecruitmentinfoLimitList`。接口有硬上限
    # （只回最新 6~10 条）且分页/检索参数无效，只能当增量源，法学过滤在本地做。
    # 武大的 corporationinfo.name 是真实单位名，北大填的是学校就业中心 → 后者从标题抽。
    dict(slug="pku", name="北京大学·就业中心", kind="frontpage", job_type=None,
         notice_kind="opening", config=dict(
             base="https://scc.pku.edu.cn",
             api="https://scc.pku.edu.cn/f/ajaxHome/ajax_findRecruitmentinfoLimitList",
             num=30, position_types=[1, 2], keep_keywords=LAW_KW,
             probe_params={"num": 30, "positionType": 1})),
    dict(slug="whu", name="武汉大学·就业中心", kind="frontpage", job_type=None,
         notice_kind="opening", config=dict(
             base="https://xsjy.whu.edu.cn",
             api="https://xsjy.whu.edu.cn/f/ajaxHome/ajax_findRecruitmentinfoLimitList",
             num=30, position_types=[1, 2], keep_keywords=LAW_KW,
             probe_params={"num": 30, "positionType": 1})),

    # ── 外校就业中心 JSON 接口（免登录，已验证）────────────────────────
    # 法学过滤在 zuel.py 里按"岗位名含法学角色词"完成：该接口的 majors 字段会把
    # 企业接受的所有专业列全（一条能列 38 个），拿它当过滤依据会把泛岗位全捞进来。
    dict(slug="zuel", name="中南财经政法大学·就业中心", kind="zuel", city=None,
         job_type=None, config=dict(
             api="https://jyzx.zuel.edu.cn/api/publicly/recruit/list",
             base="https://jyzx.zuel.edu.cn", type=1, pages=4, limit=20)),

    # ── 国企 JSON 接口（比逐家攻集团官网现实：抽查 9 家，4 家不可达、4 家 JS 渲染）
    # 省人社厅"国企招聘专区"：POST JSON 接口（从前端 chunk 逆向），按关键词分片拉取，
    # 聚合全省公共就业机构发布的国企岗位（含二级公司），当日更新
    dict(slug="ggfw_gq", name="广东省人社厅·国企招聘专区", kind="ggfw", city=None,
         job_type=None, config=dict(
             api="https://ggfw.hrss.gd.gov.cn/recruitment/internet/main/internet"
                 "/retrieval/c/recruitment/homepage/positions",
             base="https://ggfw.hrss.gd.gov.cn/recruitment/internet/main/",
             pages=2, size=50, unit_kinds="110,141,151", keep_keywords=LAW_KW)),
    # 越秀集团（大易系统）：列表接口直接给工作内容/任职要求/截止日期，
    # 聚合越秀系全部二级公司（金控/租赁/资本/服务）；positionName 服务端精准过滤
    dict(slug="yuexiu", name="越秀集团·招聘岗位", kind="hotjob", city=None,
         job_type=None, config=dict(
             api="https://yuexiu.hotjob.cn/wt/YUEXIU/web/json/position/list",
             detail_base="https://yuexiu.hotjob.cn/wt/YUEXIU/web/jobDetail",
             brand_code=1, post_type=1, pages=3, limit=50,
             position_keywords=["法务", "法律", "合规", "风控", "知识产权"],
             keep_keywords=LAW_KW)),

    # ── 西南政法大学（五院四系，单位质量高）：首页"最新职位"块 SSR 可抓；
    #    搜索页 JS 渲染抓不到，所以只有首页增量
    dict(slug="swupl", name="西南政法大学·最新职位", kind="swupl", city=None,
         job_type=None, config=dict(
             list_url="https://swupl.cqbys.com/", keep_keywords=LAW_KW)),
]

# ── 展示分组与优先级 ─────────────────────────────────────────────────────
# 用户要求"按院校层级、地区、行业/岗位类型建立分类标签与展示优先级"。
# 分组显示名与排序权重定义在 app.classify.SOURCE_CATEGORIES（单一真源），
# 这里只管"哪个源属于哪个分组"。
_SLUG_CATEGORY = {
    "tsinghua": "top-law", "pku": "top-law", "whu": "top-law",
    "swupl": "top-law", "zuel": "top-law",
    "gdufs": "gd-univ", "gzhu": "gd-univ", "gduf": "gd-univ", "gcc": "gd-univ",
    "ggfw_gq": "soe", "gzw_gd": "soe", "yuexiu": "soe", "geg": "soe",
    "gdcourts": "gov", "gd_jcy": "gov", "hrss_gd": "gov", "hrss_gz": "gov",
    "hrss_sz": "gov", "hrss_zh": "gov", "hrss_fs": "gov", "hrss_dg": "gov",
    "hrss_zs": "gov", "sg_gov": "gov", "sg_rsrc": "gov",
    "gdzz_luqu": "gov", "army_81rc": "gov",
    "fs_lvxie": "lawfirm", "gz_lvxie": "lawfirm", "sz_lvxie": "lawfirm",
    "hz_lvxie": "lawfirm", "zs_lvxie": "lawfirm", "jm_lvxie": "lawfirm",
}


def main(db_path="data/job.db"):
    conn = db.connect(db_path)
    db.init_db(conn)
    for s in SOURCES:
        cat = _SLUG_CATEGORY.get(s["slug"], "talent")
        cat_name, rank = SOURCE_CATEGORIES[cat]
        conn.execute(
            "INSERT INTO sources(slug,name,kind,city,job_type,category,rank,config) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
            "city=excluded.city, job_type=excluded.job_type, config=excluded.config, "
            "category=excluded.category, rank=excluded.rank",
            (s["slug"], s["name"], s["kind"], s.get("city"), s.get("job_type"),
             cat, rank, json.dumps(s["config"], ensure_ascii=False)))
    conn.commit()
    print(f"seeded {len(SOURCES)} sources -> {db_path}")


if __name__ == "__main__":
    main(*sys.argv[1:])
