from pathlib import Path

from app.collect import store

ITEM = {"title": "某法院招聘书记员公告", "url": "https://a.gov.cn/x/1",
        "source_slug": "gdcourts", "city": "广州", "job_type": "public",
        "publish_date": "2026-09-01", "deadline": "2026-09-20",
        "body": "<p>请于2026年9月20日前报名参加考核</p>"}


def test_insert_then_duplicate_then_merge(conn, monkeypatch, tmp_path):
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    assert store.save_item(conn, ITEM)[0] == "inserted"
    assert store.save_item(conn, ITEM)[0] == "duplicate"
    other = dict(ITEM, url="https://b.gov.cn/y/2", source_slug="hrss_gd",
                 title="某法院 招聘书记员公告")
    assert store.save_item(conn, other)[0] == "merged"
    row = conn.execute("SELECT merge_count FROM jobs").fetchone()
    assert row["merge_count"] == 2
    n = conn.execute("SELECT COUNT(*) c FROM job_sources").fetchone()["c"]
    assert n == 2
    jobs_n = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    assert jobs_n == 1


def test_search_text_and_fts(conn, monkeypatch, tmp_path):
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    store.save_item(conn, ITEM)
    row = conn.execute("SELECT search_text FROM jobs").fetchone()
    assert "报名参加考核" in row["search_text"]
    if getattr(conn, "has_fts", False):
        hits = conn.execute(
            "SELECT job_id FROM jobs_fts WHERE jobs_fts MATCH '报名参加'").fetchall()
        assert len(hits) == 1
