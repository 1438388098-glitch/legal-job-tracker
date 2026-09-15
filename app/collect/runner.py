import json
import logging
import sqlite3
from datetime import datetime

from .. import db
from . import store
from .generic_html import Adapter as HtmlAdapter

log = logging.getLogger("collect")


# 源记录上这几个列是"栏目的固有属性"（如"事业单位公开招聘"栏目里全是体制内岗位），
# 必须注入 config 才能被 enrich 读到。曾经漏掉这一步，导致源级配置形同虚设、
# 全部退回按标题猜，实测 47% 的条目落进"未分类"。
_ROW_INTO_CFG = ("city", "job_type", "org", "notice_kind")


def _source_cfg(row) -> dict:
    cfg = json.loads(row["config"] or "{}")
    keys = row.keys()
    for k in _ROW_INTO_CFG:
        if k in keys and row[k] and not cfg.get(k):
            cfg[k] = row[k]
    return cfg


def _adapter_for(row):
    cfg = _source_cfg(row)
    kind = row["kind"]
    if kind == "zuel":
        from . import zuel
        return zuel.Adapter(cfg)
    if kind == "ggfw":
        from . import ggfw
        return ggfw.Adapter(cfg)
    if kind == "hotjob":
        from . import hotjob
        return hotjob.Adapter(cfg)
    if kind == "swupl":
        from . import swupl
        return swupl.Adapter(cfg)
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
        known = {r[0] for r in self.conn.execute("SELECT url_fingerprint FROM jobs")}
        for slug in targets:
            r = self.run_source(slug, known)
            if r.get("error"):
                total["failed"] += 1
            total["inserted"] += r.get("inserted", 0)
            total["merged"] += r.get("merged", 0)
        db.auto_archive(self.conn)
        # 桌面通知由调用方（app.web.main.daily）在采集后按汇总数据决定是否发送，
        # 这里不再发，避免定时采集与手动采集重复弹窗。
        return total

    def run_source(self, slug: str, known_fps: set[str] | None = None) -> dict:
        row = self.conn.execute("SELECT * FROM sources WHERE slug=?", (slug,)).fetchone()
        if row is None:
            return {"error": f"unknown source {slug}"}
        result: dict = {"inserted": 0, "merged": 0}
        try:
            adapter = _adapter_for(row)
            for item in adapter.collect(known_fps):
                item.setdefault("source_slug", slug)
                # 适配器内部已按 cfg 填过，这里只兜住 pastebox 这类不走 enrich 的条目
                if row["city"] and not item.get("city"):
                    item["city"] = row["city"]
                if row["job_type"] and not item.get("job_type"):
                    item["job_type"] = row["job_type"]
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
