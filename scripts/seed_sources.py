"""T1 信息源配置（首批 13 个）。

选择器字段以 tests/fixtures/<slug>_list.html 真实录制页面为准校准，
校准方法：python scripts/inspect_page.py tests/fixtures/<slug>_list.html
详情页选择器 detail_sel 留空则抓取全文文本。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


def _html(slug_name, list_url, item_sel, title_sel="a", date_sel=None,
          detail_sel=None, city=None, job_type=None, **extra):
    cfg = dict(list_url=list_url, item_sel=item_sel, title_sel=title_sel,
               max_items=30, **extra)
    if date_sel:
        cfg["date_sel"] = date_sel
    if detail_sel:
        cfg["detail_sel"] = detail_sel
    return dict(kind="html", city=city, job_type=job_type, config=cfg,
                name=slug_name)


SOURCES = [
    dict(slug="gdcourts", **_html(
        "广东法院网·工作公告",
        "https://www.gdcourts.gov.cn/gsxx/fayuangonggao/index.html",
        item_sel="ul.news-list li", date_sel="span.date", detail_sel="div.article",
        job_type="public")),
    dict(slug="hrss_gd", **_html(
        "广东省人社厅·事业单位招聘公告",
        "https://hrss.gd.gov.cn/zwgk/sydwzp/zpgg/index.html",
        item_sel="ul.news-list li", date_sel="span",
        job_type="public")),
    dict(slug="hrss_gz", **_html(
        "广州市人社局·事业单位公开招聘",
        "https://rsj.gz.gov.cn/ywzt/rszdgg/sydwgkzp/",
        item_sel="ul.list li", date_sel="span",
        city="广州", job_type="public")),
    dict(slug="hrss_sz", **_html(
        "深圳市人社局·公职人员招考",
        "https://hrss.sz.gov.cn/gzryzk/",
        item_sel="ul.news-list li", date_sel="span",
        city="深圳", job_type="public")),
    dict(slug="hrss_zs", **_html(
        "中山市人社局·事业单位公开招聘",
        "http://hrss.zs.gov.cn/xxgk/rsxx/sydwgkzp/index.html",
        item_sel="ul.list li", date_sel="span",
        city="中山", job_type="public")),
    dict(slug="hrss_zh", **_html(
        "珠海市人社局·公职招考",
        "https://zhrsj.zhuhai.gov.cn/zw/tzgg/gzzk/index.html",
        item_sel="ul.list li", date_sel="span",
        city="珠海", job_type="public")),
    dict(slug="hrss_fs", **_html(
        "佛山市人社局·机关事业单位招录",
        "https://hrss.foshan.gov.cn/zwgk/jgsydwzl/index.html",
        item_sel="ul.list li", date_sel="span",
        city="佛山", job_type="public")),
    dict(slug="gd_jcy", **_html(
        "广东省检察院·通知公告",
        "http://www.gd.jcy.gov.cn/tzgg/",
        item_sel="ul.list li", date_sel="span",
        encoding="gb2312", verify=False, job_type="public")),
    dict(slug="fs_lvxie", **_html(
        "佛山市律协·招聘信息",
        "https://www.gdlawyers.net/recruit/index.html",
        item_sel="ul.list li", date_sel="span",
        city="佛山", job_type="lawfirm",
        detail_sel="div.content")),
    dict(slug="hz_lvxie", **_html(
        "惠州市律协·律所招聘",
        "https://new.hzlawyers.cn/list/recruitment_info",
        item_sel="ul.list li", date_sel="span",
        city="惠州", job_type="lawfirm")),
    dict(slug="gdufs", **_html(
        "广东外语外贸大学·招聘职位",
        "https://career.gdufs.edu.cn/job-list",
        item_sel="ul.list li", date_sel="span")),
    dict(slug="gzhu", **_html(
        "广州大学·职位信息",
        "https://jy.gzhu.edu.cn/job-list",
        item_sel="ul.list li", date_sel="span")),
    dict(slug="zuel", name="中南财经政法大学就业中心", kind="zuel", city=None,
         job_type=None, config=dict(
             api="https://jyzx.zuel.edu.cn/api/publicly/recruit/list",
             base="https://jyzx.zuel.edu.cn", type=1, pages=3, limit=20)),
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
