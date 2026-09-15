"""并发录制 T1 源的列表页 fixture 到 tests/fixtures/。失败源保留旧 fixture 不覆盖。"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collect.http import fetch  # noqa: E402
from scripts.seed_sources import SOURCES  # noqa: E402

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def grab(slug: str, url: str):
    try:
        cfg = next(s["config"] for s in SOURCES if s["slug"] == slug)
        r = fetch(url, encoding=cfg.get("encoding"), verify=cfg.get("verify", True),
                  tries=2)
        out = FIX / f"{slug}_list.html"
        out.write_bytes(r.content)
        return slug, "ok", len(r.content)
    except Exception as e:  # noqa: BLE001
        return slug, f"FAIL {type(e).__name__}: {e}", 0


def main():
    jobs = {s["slug"]: s["config"]["list_url"] for s in SOURCES if s["kind"] == "html"}
    jobs["zuel"] = SOURCES[-1]["config"]["api"]
    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(grab, slug, url): slug for slug, url in jobs.items()}
        for f in as_completed(futs):
            slug, status, size = f.result()
            results[slug] = (status, size)
            print(f"{slug:10s} {status} {size}")
    ok = [s for s, (st, _) in results.items() if st == "ok"]
    print(f"\n{len(ok)}/{len(jobs)} 成功: {', '.join(sorted(ok))}")


if __name__ == "__main__":
    main()
