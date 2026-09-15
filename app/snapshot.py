from pathlib import Path

SNAP_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def save(conn, job_id: int, body: str | None) -> str | None:
    if not body:
        return None
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{job_id}.html"
    path.write_text(body, encoding="utf-8")
    conn.execute("UPDATE jobs SET snapshot_path=? WHERE id=?", (str(path), job_id))
    conn.commit()
    return str(path)
