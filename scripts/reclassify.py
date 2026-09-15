"""用本地数据重算已有条目的派生字段（不重新联网抓取）。

适用场景：改了岗位类型 / 单位抽取 / 公告性质 / 截止日期规则后，希望存量数据跟着更新。
单位名、岗位类型都能从标题与源配置推出来，不必重新采集一遍。

用法：
    python scripts/reclassify.py              # 全量重算
    python scripts/reclassify.py --kind-only  # 只重算公告性质（最快）
    python scripts/reclassify.py --refresh-org  # 连单位名也重新抽（改了抽取规则后用）

说明：单位名默认是"粘性"的——列表页明确给出的单位名比从标题猜的更可靠，
所以已有值不会被覆盖。只有带 --refresh-org 时才会用新规则重新抽一遍
（抽不到则保留原值）。
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app import db  # noqa: E402
from app.classify import extract_org  # noqa: E402  仅 --refresh-org 重抽单位名时用
from app.collect.common import finalize  # noqa: E402  与采集同一条字段构建路径
from app.collect.runner import _source_cfg  # noqa: E402 与采集时同一套源级注入逻辑
from app.collect.store import _search_text, reindex_fts  # noqa: E402


def main(db_path: str = "data/job.db", kind_only: bool = False,
         refresh_org: bool = False):
    conn = db.connect(db_path)
    db.init_db(conn)

    # 源级固有属性（栏目性质 / 岗位类型 / 城市）——与 runner 共用一套注入逻辑，
    # 保证"重算"与"重新采集"得到的结果一致
    src: dict[str, dict] = {}
    for s in conn.execute("SELECT * FROM sources").fetchall():
        src[s["slug"]] = _source_cfg(s)

    rows = conn.execute(
        "SELECT id, title, org, city, deadline, job_type, employment_type, rolling, "
        "snapshot_path, notice_kind, source_slug FROM jobs").fetchall()
    n = Counter()
    for r in rows:
        cfg = src.get(r["source_slug"], {})
        body = ""
        p = r["snapshot_path"]
        if p and Path(p).exists():
            body = Path(p).read_text("utf-8", errors="replace")

        # 单位名默认粘性（列表页给的值优先）；--refresh-org 时按新规则重抽
        if refresh_org:
            org = extract_org(r["title"]) or cfg.get("org") or r["org"]
        else:
            org = r["org"] or cfg.get("org") or extract_org(r["title"])

        # 与采集时完全相同的 finalize，避免两处规则漂移（曾经这里无条件用
        # guess_deadline 覆盖，重算一次就把深圳律协列表页给出的准确截止日冲掉了）
        new = finalize({
            "title": r["title"],
            "org": org,
            "city": r["city"],                        # 粘性：用户手改过的不覆盖
            "employment_type": r["employment_type"],  # 同上
            "deadline": r["deadline"],                # 正文抽不到时作兜底
        }, body, cfg)
        kind, jt, city = new["notice_kind"], new["job_type"], new["city"]
        emp, rolling = new["employment_type"], new["rolling"]
        deadline = r["deadline"] if kind_only else new["deadline"]

        if kind != r["notice_kind"]:
            n["公告性质"] += 1
        if org != r["org"]:
            n["单位名"] += 1
        if jt != r["job_type"]:
            n["岗位类型"] += 1
        if city != r["city"]:
            n["城市"] += 1
        if emp != r["employment_type"]:
            n["用工性质"] += 1
        if rolling != r["rolling"]:
            n["长期有效"] += 1
        if not kind_only and deadline != r["deadline"]:
            n["截止日期"] += 1

        conn.execute(
            "UPDATE jobs SET notice_kind=?, deadline=?, org=?, job_type=?, city=?, "
            "employment_type=?, rolling=?, search_text=? WHERE id=?",
            (kind, deadline, org, jt, city, emp, rolling,
             _search_text({"title": r["title"], "org": org, "body": body,
                           "notes": None}), r["id"]))
        reindex_fts(conn, r["id"], r["title"], org, body)
    conn.commit()

    print(f"{len(rows)} 条：" + ("，".join(f"{k} 更新 {v} 条" for k, v in n.items())
                              or "无变化"))
    print("\n岗位类型分布：")
    for r in conn.execute("SELECT job_type t, COUNT(*) c FROM jobs "
                          "GROUP BY job_type ORDER BY c DESC"):
        print(f"   {r['t']:<16} {r['c']}")
    print("公告性质分布：")
    for r in conn.execute("SELECT notice_kind k, COUNT(*) c FROM jobs "
                          "GROUP BY notice_kind ORDER BY c DESC"):
        print(f"   {r['k']:<10} {r['c']}")
    print("用工性质分布：")
    for r in conn.execute("SELECT COALESCE(employment_type,'(未识别)') k, COUNT(*) c "
                          "FROM jobs GROUP BY employment_type ORDER BY c DESC"):
        print(f"   {r['k']:<10} {r['c']}")
    print(f"长期有效岗位：{conn.execute('SELECT COUNT(*) c FROM jobs WHERE rolling=1').fetchone()['c']}")


if __name__ == "__main__":
    main(*[a for a in sys.argv[1:] if not a.startswith("--")],
         kind_only="--kind-only" in sys.argv,
         refresh_org="--refresh-org" in sys.argv)
