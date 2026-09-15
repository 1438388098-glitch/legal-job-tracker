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

# 批量提交：一次冷启动要入库几百条，每条都 fsync 一次的话，光提交就占掉大半
# 耗时。攒够 BATCH_SIZE 条再落盘；调用方（runner/pastebox）结束前调 flush()。
# 数据库是 WAL 模式，中途崩溃最多丢最后这批，不会损坏已有数据。
BATCH_SIZE = 50
_PENDING: dict[int, tuple] = {}


def flush(conn: sqlite3.Connection) -> None:
    """提交所有待落盘的改动。采集结束、或需要立刻对外可见时调用。"""
    _PENDING.pop(id(conn), None)
    conn.commit()


def _commit(conn: sqlite3.Connection) -> None:
    prev = _PENDING.get(id(conn))
    n = (prev[1] if prev else 0) + 1
    _PENDING[id(conn)] = (conn, n)   # 存强引用，避免 id 被回收后复用
    if n >= BATCH_SIZE:
        flush(conn)


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

    先用 SQL 按指纹前缀预筛，再对少量候选跑相似度。title_fingerprint 是
    "单位|标题"，同一场招聘散落不同渠道时单位名必然相同，所以前缀相同是必要条件；
    不预筛的话每条新记录都要跟最近 800 条做 SequenceMatcher，量大时是采集瓶颈。
    """
    prefix = (tfp or "")[:8].replace("%", r"\%").replace("_", r"\_")
    sql = ("SELECT id, title_fingerprint, publish_date FROM jobs "
           "WHERE source_slug<>?")
    args: list = [item["source_slug"]]
    if prefix:
        sql += " AND title_fingerprint LIKE ? ESCAPE '\\'"
        args.append(prefix + "%")
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(MERGE_SCAN_LIMIT)
    for row in conn.execute(sql, args).fetchall():
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
        _commit(conn)
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
    snapshot.save(conn, job_id, item.get("body"))
    reindex_fts(conn, job_id, item["title"], item.get("org"), item.get("body") or "")
    _commit(conn)   # 一次采集数百条，每条 fsync 三次会是主要耗时
    return "inserted", job_id
