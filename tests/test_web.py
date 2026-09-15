import pytest
from fastapi.testclient import TestClient

from app.web.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DISABLE_SCHEDULER", "1")
    monkeypatch.setattr("app.snapshot.SNAP_DIR", tmp_path / "snap")
    app = create_app(str(tmp_path / "w.db"))
    app.state.conn.execute(
        "INSERT INTO sources(slug,name,kind,config) VALUES('demo','演示','html','{}')")
    app.state.conn.execute(
        "INSERT INTO jobs(title,org,job_type,city,deadline,source_slug,url,url_fingerprint,"
        "search_text) VALUES('书记员招聘','某法院','public','深圳', date('now','+2 day'),"
        "'demo','https://d/1','fp1','书记员招聘 某法院 报名2026年10月1日截止')")
    app.state.conn.commit()
    with TestClient(app) as c:
        yield c


def test_list_and_filters(client):
    r = client.get("/")
    assert r.status_code == 200 and "书记员招聘" in r.text
    r = client.get("/", params={"q": "报名"})
    assert "书记员招聘" in r.text
    r = client.get("/", params={"city": "广州"})
    assert "书记员招聘" not in r.text


def test_detail_and_status(client):
    r = client.get("/jobs/1")
    assert r.status_code == 200 and "书记员招聘" in r.text
    r = client.post("/jobs/1/status", data={"status": "read"})
    assert r.status_code in (200, 303)
    st = client.app.state.conn.execute(
        "SELECT status FROM jobs WHERE id=1").fetchone()["status"]
    assert st == "read"


def test_apply_flow(client):
    client.post("/jobs/1/apply")
    r = client.get("/board")
    assert "待投" in r.text
    aid = client.app.state.conn.execute("SELECT id FROM applications").fetchone()["id"]
    client.post(f"/applications/{aid}/status", data={"status": "已投", "note": "官网投递"})
    st = client.app.state.conn.execute(
        "SELECT status FROM applications WHERE id=?", (aid,)).fetchone()["status"]
    assert st == "已投"


def test_paste_flow(client, monkeypatch):
    monkeypatch.setattr("app.collect.pastebox.collect_url", lambda url: {
        "title": "律所实习招聘", "url": url, "source_slug": "pastebox", "org": None,
        "city": "深圳", "job_type": "intern", "publish_date": None,
        "deadline": None, "body": "正文", "status": "pending", "needs_review": True})
    r = client.post("/paste", data={"url": "https://mp.weixin.qq.com/s/x"})
    assert r.status_code in (200, 303)
    jid = client.app.state.conn.execute(
        "SELECT id FROM jobs WHERE status='pending'").fetchone()["id"]
    r = client.post(f"/jobs/{jid}/confirm", data={
        "title": "律所实习招聘(修)", "city": "深圳", "deadline": "2026-10-01",
        "job_type": "intern", "notes": ""})
    assert r.status_code in (200, 303)
    st = client.app.state.conn.execute(
        "SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()["status"]
    assert st == "new"


def test_health_page(client):
    r = client.get("/health")
    assert r.status_code == 200 and "演示" in r.text


def test_export_xlsx(client):
    r = client.get("/export.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml")
