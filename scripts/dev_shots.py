"""把本地服务页面截成图，用于改完视觉后人工核对。

为什么不是简单一句 chrome --screenshot：
  1. 页面在 headless 里的 prefers-color-scheme 恒为 dark，无法用系统偏好切换主题，
     只能临时改写 style.css 里的选择器来强制浅色/深色；
  2. 进场动画会让截图停在半透明的中途，看起来"整页发灰"，截图时必须先禁掉动画；
  3. Chrome 会缓存 CSS，所以要给页面 URL 加时间戳（模板里已带 ?v=mtime）。

脚本会在结束时还原 style.css，即使中途报错也会还原。

用法：
    python scripts/dev_shots.py --theme light --out D:/shots \
        list=/ 1400x900  detail=/jobs/1 1280x700
    python scripts/dev_shots.py --theme dark --out D:/shots list=/
"""
import argparse
import glob
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "app" / "web" / "static" / "style.css"
KILL_ANIM = "\n*,*::before,*::after{animation:none!important;transition:none!important}\n"


def find_chrome() -> str:
    for pat in ("~/.agent-browser/browsers/*/chrome.exe",
                "~/.agent-browser/browsers/*/chrome",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        hits = glob.glob(str(Path(pat).expanduser()))
        if hits:
            return sorted(hits)[-1]
    raise SystemExit("找不到 Chrome，可先跑 `agent-browser install`")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--base", default="http://127.0.0.1:8642")
    ap.add_argument("specs", nargs="+",
                    help="名称=路径，紧跟一个可选的 WxH（如 list=/ 1400x900）")
    args = ap.parse_args()

    # 把 "名称=路径" 与其后紧跟的 "WxH" 合成一条
    shots: list[tuple[str, str, str]] = []
    for tok in args.specs:
        if re.fullmatch(r"\d+x\d+", tok) and shots:
            name, path, _ = shots[-1]
            shots[-1] = (name, path, tok)
        else:
            name, _, path = tok.partition("=")
            shots.append((name, path or "/", "1400x900"))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    backup = CSS.read_text("utf-8")

    # 强制主题 + 关掉动画
    patched = backup.replace(
        ':root[data-theme="dark"]',
        ":root" if args.theme == "dark" else ':root[data-theme="__off__"]')
    CSS.write_text(patched + KILL_ANIM, "utf-8")

    try:
        for name, path, size in shots:
            dest = out / f"{name}.png"
            url = f"{args.base}{path}?_={int(time.time() * 1000)}"
            subprocess.run(
                [chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars",
                 f"--window-size={size}", f"--screenshot={dest.as_posix()}", url],
                capture_output=True, timeout=120)
            ok = dest.exists()
            print(f"  {'OK ' if ok else '失败'} {name:<12} {size:<10} "
                  f"{str(dest.stat().st_size) + ' B' if ok else ''}")
    finally:
        CSS.write_text(backup, "utf-8")
        print(f"  已还原 style.css（{args.theme} 主题截图完成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
