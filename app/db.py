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
  category TEXT NOT NULL DEFAULT '',
  rank INTEGER NOT NULL DEFAULT 50,
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
CREATE TABLE IF NOT EXISTS profile(
  id INTEGER PRIMARY KEY CHECK(id=1),   -- 单用户本地工具：只有一份画像
  name TEXT NOT NULL DEFAULT '',
  education TEXT NOT NULL DEFAULT '[]',  -- [{school, degree, major, year}]
  skills TEXT NOT NULL DEFAULT '[]',
  experiences TEXT NOT NULL DEFAULT '[]',-- [{org, role, period, desc}]
  cities TEXT NOT NULL DEFAULT '[]',
  job_types TEXT NOT NULL DEFAULT '[]',
  keywords TEXT NOT NULL DEFAULT '[]',   -- 由上面字段派生的检索词，用于匹配
  years INTEGER,                          -- 工作年限（应届为 0）
  raw_text TEXT NOT NULL DEFAULT '',
  source_file TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
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
    """打开数据库。

    WAL 是必须的：Web 请求（FastAPI 线程池）与定时采集（APScheduler 线程）共用
    这一个连接，默认的 rollback journal 下写锁会锁死整库——采集一轮要几分钟，
    期间任何一次「标已读」都会在 5 秒 busy_timeout 后抛 database is locked。
    WAL 让读不阻塞写、写不阻塞读。busy_timeout 再放宽到 10 秒兜底。
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")       # 读写不互相阻塞
    conn.execute("PRAGMA busy_timeout=10000")     # 真争用时最多等 10 秒
    conn.execute("PRAGMA synchronous=NORMAL")     # WAL 下 NORMAL 足够且快很多
    return conn


# 后续版本新增的列。CREATE TABLE IF NOT EXISTS 不会给已存在的表补列，
# 用户手上的库要能平滑升级，所以这里显式补。
_MIGRATIONS = [
    ("jobs", "notice_kind", "TEXT NOT NULL DEFAULT 'opening'"),
    ("sources", "category", "TEXT NOT NULL DEFAULT ''"),   # 展示分组
    ("sources", "rank", "INTEGER NOT NULL DEFAULT 50"),    # 展示优先级，越小越靠前
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
