"""用真实 fixture 预览每个源的解析结果（选择器质量自检）。

用法：python scripts/preview_parse.py [slug ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.collect import generic_html  # noqa: E402
from scripts.seed_sources import SOURCES  # noqa: E402


def load(slug, cfg):
    raw = Path(f"tests/fixtures/{slug}_list.html").read_bytes()
    for enc in (cfg.get("encoding"), "utf-8", "gb18030", "latin-1"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"{slug}: 无法解码")


def main(slugs):
    for s in SOURCES:
        if s["kind"] != "html" or (slugs and s["slug"] not in slugs):
            continue
        cfg = s["config"]
        if not Path(f"tests/fixtures/{s['slug']}_list.html").exists():
            continue
        items = generic_html.parse_list(load(s["slug"], cfg), cfg)
        raw_n = len(items)
        items = generic_html.apply_noise_filters(items, cfg)
        print(f"\n===== {s['slug']}  ({s['name']})  {raw_n} 条 → 过滤后 {len(items)} 条")
        for i in items[:4]:
            print(f"  [{i['publish_date'] or '  --  --  '}] {i['title'][:52]}")
            print(f"      org={i['org'] or '-'}  {i['url'][:88]}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
