def test_snapshot_save_and_none(conn, tmp_path, monkeypatch):
    import app.snapshot as snap
    monkeypatch.setattr(snap, "SNAP_DIR", tmp_path / "snapshots")
    jid = conn.execute(
        "INSERT INTO jobs(title,source_slug,url,url_fingerprint) "
        "VALUES('t','s','u','fp')").lastrowid
    p = snap.save(conn, jid, "<p>正文</p>")
    assert p
    assert (tmp_path / "snapshots" / f"{jid}.html").read_text(encoding="utf-8") == "<p>正文</p>"
    row = conn.execute("SELECT snapshot_path FROM jobs WHERE id=?", (jid,)).fetchone()
    assert row["snapshot_path"] == p
    assert snap.save(conn, jid, "") is None
