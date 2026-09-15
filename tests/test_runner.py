import json
from pathlib import Path

from app.collect import runner


def test_run_source_logs_and_health(conn, monkeypatch, tmp_path):
    conn.execute("INSERT INTO sources(slug,name,kind,config) VALUES('demo','演示','html',?)",
                 (json.dumps({"list_url": "https://demo/list", "item_sel": "li a"}),))
    import app.collect.generic_html as gh
    monkeypatch.setattr(gh.Adapter, "collect", lambda self, known_fps=None: [
        {"title": "A法院招聘公告", "url": "https://demo/1", "source_slug": "demo",
         "job_type": "public", "city": "深圳", "body": "报名截止2026年10月1日"},
        {"title": "A法院 招聘公告", "url": "https://demo/2", "source_slug": "demo",
         "job_type": "public", "city": "深圳", "body": "x"},
    ])
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    summary = runner.Runner(conn).run_source("demo")
    assert summary["inserted"] == 1 and summary["merged"] == 1
    log = conn.execute("SELECT * FROM collect_logs WHERE source_slug='demo'").fetchone()
    assert log["inserted"] == 1
    src = conn.execute("SELECT * FROM sources WHERE slug='demo'").fetchone()
    assert src["consecutive_failures"] == 0 and src["last_success_at"]


def test_failure_increments_health(conn, monkeypatch, tmp_path):
    conn.execute("INSERT INTO sources(slug,name,kind,config) VALUES('bad','坏源','html','{}')")
    import app.collect.generic_html as gh

    def boom(self, known_fps=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(gh.Adapter, "collect", boom)
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    summary = runner.Runner(conn).run_source("bad")
    assert summary["error"]
    src = conn.execute(
        "SELECT consecutive_failures, last_error FROM sources WHERE slug='bad'").fetchone()
    assert src["consecutive_failures"] == 1 and "boom" in src["last_error"]
