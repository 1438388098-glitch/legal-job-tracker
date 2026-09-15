import json
import logging
import sqlite3
from datetime import datetime

from .. import db
from . import store
from .generic_html import Adapter as HtmlAdapter

log = logging.getLogger("collect")


def _adapter_for(row):
    cfg = json.loads(row["config"] or "{}")
    if row["kind"] == "zuel":
        from . import zuel
        return zuel.Adapter(cfg)
    return HtmlAdapter(cfg)


class Runner:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def run_all(self, slugs: list[str] | None = None) -> dict:
        sql = "SELECT slug FROM sources WHERE enabled=1"
        params: list = []
        if slugs:
            sql += " AND slug IN (%s)" % ",".join("?" * len(slugs))
            params = slugs
        targets = [r["slug"] for r in self.conn.execute(sql, params).fetchall()]
        total = {"inserted": 0, "merged": 0, "failed": 0}
        for slug in targets:
            r = self.run_source(slug)
            if r.get("error"):
                total["failed"] += 1
            total["inserted"] += r.get("inserted", 0)
            total["merged"] += r.get("merged", 0)
        db.auto_archive(self.conn)
        self._notify(total)
        return total

    def run_source(self, slug: str) -> dict:
        row = self.conn.execute("SELECT * FROM sources WHERE slug=?", (slug,)).fetchone()
        if row is None:
            return {"error": f"unknown source {slug}"}
        result: dict = {"inserted": 0, "merged": 0}
        try:
            adapter = _adapter_for(row)
            for item in adapter.collect():
                item.setdefault("source_slug", slug)
                if row["city"] and not item.get("city"):
                    item["city"] = row["city"]
                res, _ = store.save_item(self.conn, item)
                if res in ("inserted", "merged"):
                    result[res] += 1
            self.conn.execute(
                "UPDATE sources SET last_success_at=?, consecutive_failures=0, last_error=NULL "
                "WHERE slug=?", (datetime.now().isoformat(timespec="seconds"), slug))
            self.conn.execute(
                "INSERT INTO collect_logs(source_slug, inserted, merged) VALUES(?,?,?)",
                (slug, result["inserted"], result["merged"]))
            self.conn.commit()
        except Exception as e:  # noqa: BLE001
            result["error"] = f"{type(e).__name__}: {e}"
            self.conn.execute(
                "UPDATE sources SET consecutive_failures=consecutive_failures+1, last_error=? "
                "WHERE slug=?", (result["error"], slug))
            self.conn.execute(
                "INSERT INTO collect_logs(source_slug, error) VALUES(?,?)",
                (slug, result["error"]))
            self.conn.commit()
            log.exception("source %s failed", slug)
        return result

    def _notify(self, total: dict) -> None:
        if total.get("inserted", 0) <= 0:
            return
        if db.get_setting(self.conn, "toast_enabled", "0") != "1":
            return
        try:
            from win11toast import toast
            toast("招聘采集完成", f"新增 {total['inserted']} 条，合并 {total['merged']} 条")
        except Exception:  # noqa: BLE001 未安装 toast 附加依赖则跳过
            pass
