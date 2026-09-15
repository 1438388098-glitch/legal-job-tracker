from app import db


def test_init_creates_tables(conn):
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert {"sources", "jobs", "job_sources", "applications",
            "collect_logs", "settings"} <= names


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
