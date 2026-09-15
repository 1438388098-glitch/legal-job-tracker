import json
from pathlib import Path

from app.collect import runner


def test_source_row_fields_reach_adapter_config(conn):
    """源记录上的 city/job_type 必须注入到采集器 config。

    曾经漏了这一步：seed_sources 把这些放在源记录顶层，而 _adapter_for 只把
    config 传给适配器，于是"源级岗位类型"形同虚设、全部退回按标题猜 ——
    实测让人社厅栏目的 47% 条目落进"未分类"。
    """
    conn.execute(
        "INSERT INTO sources(slug,name,kind,city,job_type,config) "
        "VALUES('demo','演示','html','佛山','public',?)",
        (json.dumps({"list_url": "https://demo/list"}),))
    row = conn.execute("SELECT * FROM sources WHERE slug='demo'").fetchone()
    cfg = runner._source_cfg(row)
    assert cfg["city"] == "佛山"
    assert cfg["job_type"] == "public"
    assert cfg["list_url"] == "https://demo/list"   # 原有 config 不能被冲掉


def test_notice_kind_from_config(conn):
    """notice_kind 只在 config 里（sources 表没有这列），要能正常带出来。"""
    conn.execute(
        "INSERT INTO sources(slug,name,kind,config) VALUES('demo','演示','html',?)",
        (json.dumps({"list_url": "https://demo/list", "notice_kind": "opening"}),))
    row = conn.execute("SELECT * FROM sources WHERE slug='demo'").fetchone()
    assert runner._source_cfg(row)["notice_kind"] == "opening"


def test_source_config_does_not_override_explicit_values(conn):
    """config 里已经写死的值优先——某些栏目需要单独指定，不能被源级默认覆盖。"""
    conn.execute(
        "INSERT INTO sources(slug,name,kind,job_type,config) "
        "VALUES('demo','演示','html','public',?)",
        (json.dumps({"list_url": "https://demo/list", "job_type": "lawfirm"}),))
    row = conn.execute("SELECT * FROM sources WHERE slug='demo'").fetchone()
    assert runner._source_cfg(row)["job_type"] == "lawfirm"


def test_enrich_fills_org_and_type_from_source_config():
    """源级配置生效后，enrich 不该再去猜标题。"""
    from app.collect.generic_html import enrich

    cfg = {"city": "佛山", "job_type": "public"}
    item = enrich({"title": "2026年公开招聘工作人员公告",
                   "url": "https://x/1", "org": None}, "", cfg)
    assert item["job_type"] == "public"      # 靠标题猜会是 unknown
    assert item["city"] == "佛山"
    assert item["org"] is None               # 标题里确实没有单位名，留空而不是瞎猜


def test_run_source_logs_and_health(conn, monkeypatch, tmp_path):
    conn.execute("INSERT INTO sources(slug,name,kind,config) VALUES('demo','演示','html',?)",
                 (json.dumps({"list_url": "https://demo/list", "item_sel": "li a"}),))
    import app.collect.generic_html as gh
    # 第二条来自另一渠道（source_slug 不同）且标题够长 → 应当合并为一条
    monkeypatch.setattr(gh.Adapter, "collect", lambda self, known_fps=None: [
        {"title": "某市中级人民法院2026年公开招聘劳动合同制书记员公告",
         "url": "https://demo/1", "source_slug": "demo",
         "job_type": "public", "city": "深圳", "body": "报名截止2026年10月1日"},
        {"title": "某市中级人民法院2026年公开招聘劳动合同制书记员公告",
         "url": "https://demo/2", "source_slug": "other",
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
