import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'html',
  city TEXT,
  job_type TEXT,
  config TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1,
  last_success_at TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  org TEXT,
  job_type TEXT NOT NULL DEFAULT 'unknown',
  city TEXT,
  publish_date TEXT,
  deadline TEXT,
  source_slug TEXT NOT NULL,
  url TEXT NOT NULL,
  url_fingerprint TEXT NOT NULL,
  title_fingerprint TEXT,
  snapshot_path TEXT,
  legal_cert_required TEXT,
  notes TEXT,
  search_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new',
  needs_review INTEGER NOT NULL DEFAULT 0,
  notice_kind TEXT NOT NULL DEFAULT 'opening',
  employment_type TEXT,
  rolling INTEGER NOT NULL DEFAULT 0,
  merge_count INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_urlfp ON jobs(url_fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON jobs(deadline);
CREATE INDEX IF NOT EXISTS idx_jobs_kind ON jobs(notice_kind);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE TABLE IF NOT EXISTS job_sources(
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  source_slug TEXT NOT NULL,
  url TEXT NOT NULL,
  PRIMARY KEY(job_id, url)
);
CREATE TABLE IF NOT EXISTS applications(
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT '待投',
  timeline TEXT NOT NULL DEFAULT '[]',
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS collect_logs(
  id INTEGER PRIMARY KEY,
  source_slug TEXT NOT NULL,
  ran_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  inserted INTEGER NOT NULL DEFAULT 0,
  merged INTEGER NOT NULL DEFAULT 0,
  error TEXT
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# 后续版本新增的列。CREATE TABLE IF NOT EXISTS 不会给已存在的表补列，
# 用户手上的库要能平滑升级，所以这里显式补。
_MIGRATIONS = [
    ("jobs", "notice_kind", "TEXT NOT NULL DEFAULT 'opening'"),
    ("jobs", "employment_type", "TEXT"),
    ("jobs", "rolling", "INTEGER NOT NULL DEFAULT 0"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    """给已存在的老表补列。只处理已存在的表（新库交给 SCHEMA 建）。
    必须在 executescript(SCHEMA) 之前跑：SCHEMA 里含依赖新列的索引。"""
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table, col, decl in _MIGRATIONS:
        if table not in existing:
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def init_db(conn: sqlite3.Connection) -> None:
    _migrate(conn)
    conn.executescript(SCHEMA)
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5("
            "title, org, body, job_id UNINDEXED, tokenize='trigram')")
        set_setting(conn, "_has_fts", "1")
    except sqlite3.OperationalError:
        set_setting(conn, "_has_fts", "0")
    conn.commit()


def has_fts(conn: sqlite3.Connection) -> bool:
    return get_setting(conn, "_has_fts", "0") == "1"


def auto_archive(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "UPDATE jobs SET status='archived' WHERE status IN ('new','read','pending') "
        "AND deadline IS NOT NULL AND deadline < date('now','-7 day')")
    conn.commit()
    return cur.rowcount


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
