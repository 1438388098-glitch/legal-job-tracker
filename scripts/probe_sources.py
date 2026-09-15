"""从真实 fixture 中推断列表容器/日期选择器候选。

用法：
    python scripts/probe_sources.py [slug ...]

对每个 fixture 统计所有 <li>/<tr>/<div> 的 (tag, class) 组合，找出
「包含带 href 的链接、且链接有像标题的文本」最多的那些容器，
并给出其中的日期文本样本，用于人工确认 date_sel。
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from selectolax.parser import HTMLParser  # noqa: E402

DATE_RE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")
SKIP_CLS = re.compile(r"(nav|menu|crumb|footer|header|banner|search|tab|pagin|share|side)", re.I)


def key_of(node):
    tag = node.tag
    cls = (node.attributes.get("class") or "").strip().split()
    cls = ".".join(c for c in cls[:2] if not SKIP_CLS.search(c))
    return f"{tag}.{cls}" if cls else tag


def probe(slug: str):
    path = Path(f"tests/fixtures/{slug}_list.html")
    if not path.exists():
        print(f"\n##### {slug}: fixture 不存在")
        return
    html = path.read_text("utf-8", errors="replace")
    tree = HTMLParser(html)
    groups = defaultdict(list)
    for node in tree.css("li, tr, div"):
        a = node.css_first("a[href]")
        if a is None:
            continue
        text = a.text(strip=True)
        if len(text) < 8:
            continue
        groups[key_of(node)].append(node)

    print(f"\n##### {slug}  (len={len(html)})")
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))[:6]
    for sel, nodes in ranked:
        sample = nodes[0]
        a = sample.css_first("a[href]")
        title = a.text(strip=True)[:46]
        href = (a.attributes.get("href") or "")[:70]
        # 日期候选：容器内所有文本片段里第一个像日期的
        dsel, dtext = "-", "-"
        for cand in sample.css("*"):
            t = cand.text(strip=True) if not cand.css("*") else ""
            if t and DATE_RE.search(t) and len(t) < 30:
                cls = (cand.attributes.get("class") or "").strip()
                dsel = f"{cand.tag}.{cls.split()[0]}" if cls else cand.tag
                dtext = t
                break
        if dsel == "-":
            m = DATE_RE.search(sample.text(separator=" ", strip=True))
            if m:
                dsel, dtext = "(容器内文本)", m.group(0)
        print(f"  n={len(nodes):<4} sel={sel:<34} date={dsel:<22} {dtext:<14}")
        print(f"        └ {title}  ->  {href}")


if __name__ == "__main__":
    slugs = sys.argv[1:]
    if not slugs:
        slugs = sorted(p.name[:-10] for p in Path("tests/fixtures").glob("*_list.html"))
    for s in slugs:
        probe(s)
