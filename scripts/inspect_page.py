"""打印 fixture 页面的候选列表结构，用于确定 item_sel/title_sel/date_sel。"""
import sys
from pathlib import Path

from selectolax.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")


def main():
    src = Path(sys.argv[1]).read_text("utf-8", errors="replace")
    tree = HTMLParser(src)
    print("== 含 <a> 的直接父容器（按条数排序，前 15 个）==")
    buckets = {}
    for a in tree.css("a[href]"):
        p = a.parent
        if p is None:
            continue
        key = (p.tag, p.attributes.get("class"))
        buckets.setdefault(key, []).append(a)
    for (tag, cls), nodes in sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:15]:
        first = nodes[0]
        print(f"{len(nodes):4d}  <{tag} class='{cls}'> 首条: {(first.text(strip=True) or '')[:36]!r}")
    print("\n== 疑似日期元素（class 含 date/time，或文本像日期，前 15 个）==")
    n = 0
    for node in tree.css("span,em,div,td,li,time,p"):
        cls = node.attributes.get("class") or ""
        t = (node.text(strip=True) or "")[:30]
        if not t:
            continue
        if ("date" in cls.lower() or "time" in cls.lower()
                or __import__("re").search(r"20\d{2}[-/.年]", t)):
            print(f"  <{node.tag} class='{cls}'> {t!r}")
            n += 1
            if n >= 15:
                break


if __name__ == "__main__":
    main()
