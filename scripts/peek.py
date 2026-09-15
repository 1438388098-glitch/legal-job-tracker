"""按关键词打印 fixture 中的原始 HTML 片段，用于人工确认选择器。

用法：
    python scripts/peek.py <slug> <keyword|regex> [前后字符数]

支持 --enc=gb2312 指定解码。多个 fixture 会按 slug 自动匹配编码。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

ENC = {"gd_jcy": "gb2312", "hz_lvxie": "utf-8"}


def main():
    slug = sys.argv[1]
    pat = sys.argv[2]
    span = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    raw = Path(f"tests/fixtures/{slug}_list.html").read_bytes()
    enc = ENC.get(slug, "utf-8")
    for e in (enc, "utf-8", "gb18030", "latin-1"):
        try:
            html = raw.decode(e)
            break
        except UnicodeDecodeError:
            continue
    print(f"[{slug}] decoded as {e}, {len(html)} chars")
    n = 0
    for m in re.finditer(pat, html):
        i = m.start()
        seg = html[max(0, i - span // 3): i + span].replace("\n", " ")
        seg = re.sub(r"\s{2,}", " ", seg)
        print(f"--- hit {n} @{i} ---\n{seg}\n")
        n += 1
        if n >= 6:
            break
    if n == 0:
        print("no match")


if __name__ == "__main__":
    main()
