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
        # frontpage 等平台校验 Referer（缺了直接 404），带上再说；
        # 接口型源可能还要求查询参数（如 num/positionType），从 probe_params 读
        headers = {"Referer": cfg.get("referer")
                   or (cfg.get("base", "").rstrip("/") + "/")}
        r = fetch(url, params=cfg.get("probe_params"),
                  encoding=cfg.get("encoding"), verify=cfg.get("verify", True),
                  headers=headers, tries=2)
        out = FIX / f"{slug}_list.html"
        out.write_bytes(r.content)
        return slug, "ok", len(r.content)
    except Exception as e:  # noqa: BLE001
        return slug, f"FAIL {type(e).__name__}: {e}", 0


def main():
    # 各 kind 的入口：html 走列表首页，接口型源直接抓 api 存为 fixture（供回归对照）。
    # ggfw 是 POST 接口（GET 会 500），fixture 由真实采集时落库，这里跳过。
    jobs: dict[str, str] = {}
    for s in SOURCES:
        if s["kind"] == "ggfw":
            continue
        cfg = s["config"]
        url = cfg.get("list_url") or cfg.get("api")
        if s["kind"] == "html" and cfg.get("list_urls"):
            url = cfg["list_urls"][0]
        if url:
            jobs[s["slug"]] = url
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
