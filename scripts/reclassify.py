"""规则变更后，用本地 HTML 快照重算已有条目的派生字段（不重新联网抓取）。

适用场景：改了 notice_kind 判定规则、或改了截止日期推断规则后，希望存量数据
跟着更新，而不必重新采集一遍。

用法：
    python scripts/reclassify.py              # 重算公告性质 + 截止日期
    python scripts/reclassify.py --kind-only  # 只重算公告性质
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app import db  # noqa: E402
from app.classify import infer_notice_kind  # noqa: E402
from app.dateparse import guess_deadline  # noqa: E402
from app.collect.store import _search_text  # noqa: E402


def main(db_path: str = "data/job.db", kind_only: bool = False):
    conn = db.connect(db_path)
    db.init_db(conn)
    # 源级覆盖：职位板/律所招聘栏目里的条目本身就是开放岗位，不用标题猜
    override = {}
    for s in conn.execute("SELECT slug, config FROM sources").fetchall():
        fix = (json.loads(s["config"] or "{}")).get("notice_kind")
        if fix:
            override[s["slug"]] = fix

    rows = conn.execute(
        "SELECT id, title, org, deadline, snapshot_path, notice_kind, source_slug "
        "FROM jobs").fetchall()
    kind_n = dl_n = 0
    for r in rows:
        body = ""
        p = r["snapshot_path"]
        if p and Path(p).exists():
            body = Path(p).read_text("utf-8", errors="replace")
        kind = override.get(r["source_slug"]) or infer_notice_kind(r["title"], body)
        new_dl = r["deadline"] if kind_only else guess_deadline(body)
        if kind != r["notice_kind"]:
            kind_n += 1
        if not kind_only and new_dl != r["deadline"]:
            dl_n += 1
        conn.execute(
            "UPDATE jobs SET notice_kind=?, deadline=?, search_text=? WHERE id=?",
            (kind, new_dl, _search_text({"title": r["title"], "org": r["org"], "body": body}),
             r["id"]))
    conn.commit()
    print(f"{len(rows)} 条：公告性质更新 {kind_n} 条"
          + ("" if kind_only else f"，截止日期更新 {dl_n} 条"))
    for r in conn.execute("SELECT notice_kind k, COUNT(*) n FROM jobs "
                          "GROUP BY notice_kind ORDER BY n DESC"):
        print(f"   {r['k']:<9} {r['n']}")


if __name__ == "__main__":
    main(*[a for a in sys.argv[1:] if not a.startswith("--")],
         kind_only="--kind-only" in sys.argv)
