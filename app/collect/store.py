import re
import sqlite3

from .. import db as appdb
from .. import snapshot
from ..classify import NOTICE_OPENING
from ..dedup import (date_compatible, is_same_job, title_fingerprint,
                     url_fingerprint)

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")
MERGE_SCAN_LIMIT = 800


def _search_text(item: dict) -> str:
    # notes 也进搜索文本：用户自己写的备注（"已联系学长""需 A 证"）必须搜得到
    raw = (f"{item['title']} {item.get('org') or ''} {item.get('body') or ''} "
           f"{item.get('notes') or ''}")
    text = _TAGS.sub(" ", raw)
    return _SPACES.sub(" ", text).strip()


def reindex_fts(conn: sqlite3.Connection, job_id: int, title: str, org, body: str) -> None:
    if not appdb.has_fts(conn):
        return
    conn.execute("DELETE FROM jobs_fts WHERE job_id=?", (job_id,))
    conn.execute("INSERT INTO jobs_fts(title, org, body, job_id) VALUES(?,?,?,?)",
                 (title, org or "", body or "", job_id))


def find_merge_target(conn: sqlite3.Connection, item: dict, tfp: str):
    """找可合并的已有条目：只跨源合并（同源不同 URL 视为不同稿件）。

    规则见 app/dedup.py 顶部注释——跨源 + 标题够长 + 高度相似 + 发布时间接近。
    """
    for row in conn.execute(
            "SELECT id, title_fingerprint, publish_date FROM jobs "
            "WHERE source_slug<>? ORDER BY id DESC LIMIT ?",
            (item["source_slug"], MERGE_SCAN_LIMIT)).fetchall():
        if is_same_job(tfp, row["title_fingerprint"] or "") and \
                date_compatible(item.get("publish_date"), row["publish_date"]):
            return row
    return None


def save_item(conn: sqlite3.Connection, item: dict) -> tuple[str, int | None]:
    """返回 (inserted|merged|duplicate, job_id)。"""
    slug = item["source_slug"]
    urlfp = url_fingerprint(item["url"])
    row = conn.execute("SELECT id FROM jobs WHERE url_fingerprint=?", (urlfp,)).fetchone()
    if row:
        return "duplicate", row["id"]
    tfp = title_fingerprint(item.get("org") or "", item["title"])
    target = find_merge_target(conn, item, tfp)
    if target is not None:
        jid = target["id"]
        conn.execute(
            "INSERT OR IGNORE INTO job_sources(job_id,source_slug,url) VALUES(?,?,?)",
            (jid, slug, item["url"]))
        conn.execute(
            "UPDATE jobs SET merge_count=merge_count+1, deadline=COALESCE(deadline,?) WHERE id=?",
            (item.get("deadline"), jid))
        conn.commit()
        return "merged", jid
    cur = conn.execute(
        "INSERT INTO jobs(title,org,job_type,city,publish_date,deadline,source_slug,url,"
        "url_fingerprint,title_fingerprint,search_text,status,needs_review,notice_kind,"
        "employment_type,rolling) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (item["title"], item.get("org"), item.get("job_type") or "unknown", item.get("city"),
         item.get("publish_date"), item.get("deadline"), slug, item["url"], urlfp, tfp,
         _search_text(item), item.get("status") or "new", 1 if item.get("needs_review") else 0,
         item.get("notice_kind") or NOTICE_OPENING,
         item.get("employment_type"), 1 if item.get("rolling") else 0))
    job_id = cur.lastrowid
    conn.execute("INSERT INTO job_sources(job_id,source_slug,url) VALUES(?,?,?)",
                 (job_id, slug, item["url"]))
    conn.commit()
    snapshot.save(conn, job_id, item.get("body"))
    reindex_fts(conn, job_id, item["title"], item.get("org"), item.get("body") or "")
    conn.commit()
    return "inserted", job_id
