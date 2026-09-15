"""从 style.css 里解析出明暗两套配色，计算关键前景/背景组合的对比度。

为什么需要它：截图的观感只能靠眼睛，而"小字看不看得清"是可以用 WCAG 对比度
客观判定的。正文与次要文字按 4.5:1（AA，小字）要求，横幅等大字号按 3:1。

用法：python scripts/contrast_check.py
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app" / "web" / "static" / "style.css"

# (前景变量, 背景变量, 用途, 最低要求)
PAIRS = [
    ("fg", "bg", "正文 / 页面底", 4.5),
    ("fg", "bg-sub", "正文 / 次级面板", 4.5),
    ("fg", "bg-inset", "正文 / 表头底", 4.5),
    ("fg-2", "bg", "次要文字 / 页面底", 4.5),
    ("fg-3", "bg", "辅助文字 / 页面底", 4.5),
    ("fg-3", "bg-sub", "辅助文字 / 次级面板", 4.5),
    ("fg-3", "bg-inset", "辅助文字 / 表头底", 4.5),
    ("accent", "bg", "链接 / 页面底", 4.5),
    ("accent", "accent-soft", "选中导航项", 4.5),
    ("danger", "danger-bg", "临期红 / 警示底", 4.5),
    ("warn", "warn-bg", "临期黄 / 警示底", 4.5),
    ("t-lawfirm", "bg", "类型点·律所", 3.0),
    ("t-public", "bg", "类型点·体制内", 3.0),
    ("t-counsel", "bg", "类型点·法务", 3.0),
    ("t-intern", "bg", "类型点·实习", 3.0),
]


def lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def block_vars(css: str, selector: str) -> dict:
    """取某个选择器块里的 --var: #hex 定义。"""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    if not m:
        raise SystemExit(f"在 style.css 里找不到选择器 {selector}")
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{3,8})", m.group(1)))


def main() -> int:
    css = CSS.read_text("utf-8")
    schemes = {
        "浅色": block_vars(css, ":root"),
        "深色": block_vars(css, ':root[data-theme="dark"]'),
    }

    bad = 0
    for name, vars_ in schemes.items():
        print(f"\n=== {name}主题 ===")
        for fg, bg, label, need in PAIRS:
            if fg not in vars_ or bg not in vars_:
                print(f"  ?  {label:<20} 变量缺失 ({fg}/{bg})")
                continue
            r = ratio(vars_[fg], vars_[bg])
            ok = r >= need
            if not ok:
                bad += 1
            mark = "OK " if ok else "不足"
            print(f"  {mark} {label:<20} {r:5.2f}:1  (需 {need})  "
                  f"{vars_[fg]} on {vars_[bg]}")

    print(f"\n合计不达标 {bad} 项" if bad else "\n全部达标")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
