from app import db


def test_init_creates_tables(conn):
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert {"sources", "jobs", "job_sources", "applications",
            "collect_logs", "settings"} <= names


def test_migrate_adds_missing_column():
    """老库（缺 notice_kind）执行 init_db 后应自动补列，而不是整库报废。"""
    import sqlite3
    old = sqlite3.connect(":memory:")
    old.row_factory = sqlite3.Row
    old.executescript("""
        CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'html', city TEXT,
            job_type TEXT, config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1, last_success_at TEXT,
            consecutive_failures INTEGER NOT NULL DEFAULT 0, last_error TEXT);
        CREATE TABLE jobs(id INTEGER PRIMARY KEY, title TEXT NOT NULL, org TEXT,
            job_type TEXT NOT NULL DEFAULT 'unknown', city TEXT, publish_date TEXT,
            deadline TEXT, source_slug TEXT NOT NULL, url TEXT NOT NULL,
            url_fingerprint TEXT NOT NULL, title_fingerprint TEXT,
            snapshot_path TEXT, legal_cert_required TEXT, notes TEXT,
            search_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',
            needs_review INTEGER NOT NULL DEFAULT 0,
            merge_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    """)
    old.execute("INSERT INTO jobs(title,url,url_fingerprint,source_slug) "
                "VALUES('老数据','https://d/1','fp','demo')")
    old.commit()
    db.init_db(old)
    cols = {r[1] for r in old.execute("PRAGMA table_info(jobs)")}
    assert "notice_kind" in cols
    assert old.execute("SELECT notice_kind FROM jobs").fetchone()["notice_kind"] == "opening"
    db.init_db(old)  # 幂等：再跑一次不应报错


def test_auto_archive_after_7_days(conn):
    conn.execute("INSERT INTO jobs(title,source_slug,url,url_fingerprint,status,deadline) "
                 "VALUES('t','s','u','fp1','new', date('now','-8 day'))")
    conn.execute("INSERT INTO jobs(title,source_slug,url,url_fingerprint,status,deadline) "
                 "VALUES('t2','s','u2','fp2','new', date('now','+1 day'))")
    db.auto_archive(conn)
    st = {r[0] for r in conn.execute("SELECT status FROM jobs")}
    assert st == {"new", "archived"}


def test_settings(conn):
    assert db.get_setting(conn, "toast_enabled", "0") == "0"
    db.set_setting(conn, "toast_enabled", "1")
    assert db.get_setting(conn, "toast_enabled", "0") == "1"
