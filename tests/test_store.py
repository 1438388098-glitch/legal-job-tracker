from pathlib import Path

from app.collect import store

ITEM = {"title": "某市中级人民法院2026年公开招聘劳动合同制书记员公告",
        "url": "https://a.gov.cn/x/1",
        "source_slug": "gdcourts", "city": "广州", "job_type": "public",
        "publish_date": "2026-09-01", "deadline": "2026-09-20",
        "body": "<p>请于2026年9月20日前报名参加考核</p>"}


def test_insert_then_duplicate_then_merge(conn, monkeypatch, tmp_path):
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    assert store.save_item(conn, ITEM)[0] == "inserted"
    assert store.save_item(conn, ITEM)[0] == "duplicate"
    other = dict(ITEM, url="https://b.gov.cn/y/2", source_slug="hrss_gd",
                 title="某市中级人民法院2026年公开招聘劳动合同制书记员公告 ")
    assert store.save_item(conn, other)[0] == "merged"
    row = conn.execute("SELECT merge_count FROM jobs").fetchone()
    assert row["merge_count"] == 2
    n = conn.execute("SELECT COUNT(*) c FROM job_sources").fetchone()["c"]
    assert n == 2
    jobs_n = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    assert jobs_n == 1


def test_same_source_never_merges(conn, monkeypatch, tmp_path):
    """同源不同 URL 就是不同稿件：同一批招聘的分期公示不能被合成一条。"""
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    for i in (1, 2):
        it = dict(ITEM, url=f"https://a.gov.cn/x/{i}")
        assert store.save_item(conn, it)[0] == "inserted"
    assert conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 2


def test_generic_title_not_merged_cross_source(conn, monkeypatch, tmp_path):
    """跨源但标题是泛岗位名（律师助理），也不能合并——那是不同律所的岗位。"""
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    a = dict(ITEM, title="律师助理", url="https://a.cn/1", source_slug="gdufs")
    b = dict(ITEM, title="律师助理", url="https://b.cn/2", source_slug="gzhu")
    assert store.save_item(conn, a)[0] == "inserted"
    assert store.save_item(conn, b)[0] == "inserted"


def test_distant_publish_date_not_merged(conn, monkeypatch, tmp_path):
    """跨源长标题相同但年份差三年——是不同届的公告，不合并。"""
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    a = dict(ITEM, url="https://a.cn/1", source_slug="gdcourts", publish_date="2023-03-08")
    b = dict(ITEM, url="https://b.cn/2", source_slug="hrss_gd", publish_date="2026-01-22")
    assert store.save_item(conn, a)[0] == "inserted"
    assert store.save_item(conn, b)[0] == "inserted"


def test_search_text_and_fts(conn, monkeypatch, tmp_path):
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    store.save_item(conn, ITEM)
    row = conn.execute("SELECT search_text FROM jobs").fetchone()
    assert "报名参加考核" in row["search_text"]
    if getattr(conn, "has_fts", False):
        hits = conn.execute(
            "SELECT job_id FROM jobs_fts WHERE jobs_fts MATCH '报名参加'").fetchall()
        assert len(hits) == 1
