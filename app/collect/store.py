import re
import sqlite3

from .. import db as appdb
from .. import snapshot
from ..dedup import is_same_title, title_fingerprint, url_fingerprint

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def _search_text(item: dict) -> str:
    raw = f"{item['title']} {item.get('org') or ''} {item.get('body') or ''}"
    text = _TAGS.sub(" ", raw)
    return _SPACES.sub(" ", text).strip()


def reindex_fts(conn: sqlite3.Connection, job_id: int, title: str, org, body: str) -> None:
    if not appdb.has_fts(conn):
        return
    conn.execute("DELETE FROM jobs_fts WHERE job_id=?", (job_id,))
    conn.execute("INSERT INTO jobs_fts(title, org, body, job_id) VALUES(?,?,?,?)",
                 (title, org or "", body or "", job_id))


def save_item(conn: sqlite3.Connection, item: dict) -> tuple[str, int | None]:
    """返回 (inserted|merged|duplicate, job_id)。"""
    slug = item["source_slug"]
    urlfp = url_fingerprint(item["url"])
    row = conn.execute("SELECT id FROM jobs WHERE url_fingerprint=?", (urlfp,)).fetchone()
    if row:
        return "duplicate", row["id"]
    tfp = title_fingerprint(item.get("org") or "", item["title"])
    for jid, jtfp in conn.execute(
            "SELECT id, title_fingerprint FROM jobs ORDER BY id DESC LIMIT 500").fetchall():
        if jtfp and is_same_title(tfp, jtfp):
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
        "url_fingerprint,title_fingerprint,search_text,status,needs_review) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (item["title"], item.get("org"), item.get("job_type") or "unknown", item.get("city"),
         item.get("publish_date"), item.get("deadline"), slug, item["url"], urlfp, tfp,
         _search_text(item), item.get("status") or "new", 1 if item.get("needs_review") else 0))
    job_id = cur.lastrowid
    conn.execute("INSERT INTO job_sources(job_id,source_slug,url) VALUES(?,?,?)",
                 (job_id, slug, item["url"]))
    conn.commit()
    snapshot.save(conn, job_id, item.get("body"))
    reindex_fts(conn, job_id, item["title"], item.get("org"), item.get("body") or "")
    conn.commit()
    return "inserted", job_id
