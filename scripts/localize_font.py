"""把中文字体按需本地化：只下载页面实际用得到的字片。

为什么不用 CDN：这是本地单机工具，断网也要能正常显示，且不该每次开页面都
等网络。fontsource 的 Noto Sans SC 按 unicode-range 切成 101 片，我们只取与页面
字符集有交集的那几十片，本地托管。

选思源黑体而非衬线体：界面定位是高信息密度的工具，小字号中文衬线在屏上发糊；
黑体字形均匀、字面紧凑，同宽度能塞下更多字。

字符集来源：数据库里所有岗位标题/单位 + 模板与源码里的静态文案 + ASCII/标点。

用法：
    python scripts/localize_font.py [--force]
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import httpx  # noqa: E402

PKG = "noto-sans-sc"
FAMILY = "Noto Sans SC"
WEIGHTS = [400, 600]
CDN = f"https://cdn.jsdelivr.net/npm/@fontsource/{PKG}"
OUT = Path("app/web/static/fonts")
CSS_OUT = Path("app/web/static/fonts.css")
DB = "data/job.db"

# 界面里会出现的固定文案（模板之外的动态内容都来自数据库，已单独收集）
EXTRA = (
    "法学招聘信息中台岗位列表我的投递粘贴箱源健康设置导出可投递全部稿件"
    "筛选重置全部类型城市状态公告性质只看关键词搜索标题单位正文暂无"
    "去页点立即采集或在粘入公众号文章链接新已读待确认归档恢复编辑截止"
    "发布日期性质链接备注序号时间最近成功连续失败次数错误操作返回保存"
    "确认取消提交申请面试笔试待投拒备注备注类型律所体制内法务实习未分类"
    "广州深圳珠海佛山惠州东莞中山江门肇庆韶关个来源结果公示其他信息"
    "我要投关闭打开查看详情快照正文来源原文原网页已存在抓取失败请重试"
    "开启通知每日自动采集说明本机数据不上传任何服务器隐私安全"
)


def collect_chars() -> set[str]:
    chars: set[str] = set(EXTRA)
    # ASCII 可见字符 + 常用中英文标点 + 数字
    chars |= set(chr(c) for c in range(0x20, 0x7F))
    chars |= set("　、。〈〉《》「」『』【】〔〕・ー—–…‘’“”·×÷±°"
                 "！？，．：；（）［］｛｝％＃＠＆＊＋－／＝＼｜～￥")
    chars |= set("０１２３４５６７８９")
    # 模板与源码里的所有文本
    for pat in ("app/web/templates/**/*.html", "app/**/*.py", "scripts/*.py"):
        for p in Path(".").glob(pat):
            try:
                chars |= set(p.read_text("utf-8", errors="ignore"))
            except OSError:
                pass
    # 数据库里的动态内容
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        for title, org, notes in c.execute("SELECT title, org, notes FROM jobs"):
            chars |= set(title or "")
            chars |= set(org or "")
            chars |= set(notes or "")
    except Exception as e:  # noqa: BLE001
        print(f"  (跳过我数据库字符收集：{e})")
    return {ch for ch in chars if ch.strip() or ch == " "}


def parse_ranges(css: str, weight: int) -> list[tuple[str, str]]:
    """返回 [(woff2 文件名, unicode-range 字符串)]，只取指定字重。"""
    out = []
    for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
        if f"font-weight: {weight}" not in block:
            continue
        m = re.search(r"url\(\./files/([^)]+\.woff2)\)", block)
        ur = re.search(r"unicode-range:\s*([^;}]+)", block)
        if m and ur:
            out.append((m.group(1), ur.group(1)))
    return out


def range_covers(rng: str, codepoints: set[int]) -> bool:
    for part in rng.split(","):
        part = part.strip().upper().lstrip("U")
        if not part:
            continue
        part = part.lstrip("+")
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a, 16), int(b, 16)
        else:
            lo = hi = int(part, 16)
        # 用二分思路快速判断：只要区间内有一个待渲染字符即需要该片
        for cp in codepoints:
            if lo <= cp <= hi:
                return True
    return False


def fetch_weight_css(weight: int) -> str:
    """fontsource 的 index.css 只含默认字重，其他字重要取 <weight>.css。"""
    for path in (f"{weight}.css", "index.css"):
        r = httpx.get(f"{CDN}/{path}", timeout=30, follow_redirects=True)
        if r.status_code == 200 and f"font-weight: {weight}" in r.text:
            return r.text
    return ""


def main(force: bool = False):
    chars = collect_chars()
    cps = {ord(c) for c in chars}
    print(f"页面字符集：{len(chars)} 个不同字符")

    OUT.mkdir(parents=True, exist_ok=True)
    css_by_weight: dict[int, str] = {}
    jobs: list[tuple[str, str, int]] = []
    for w in WEIGHTS:
        css = fetch_weight_css(w)
        if not css:
            print(f"  字重 {w}: 取不到 CSS，跳过")
            continue
        css_by_weight[w] = css
        ranges = parse_ranges(css, w)
        need = [(f, r) for f, r in ranges if range_covers(r, cps)]
        print(f"  字重 {w}: 共 {len(ranges)} 片，需要 {len(need)} 片")
        jobs.extend((f, r, w) for f, r in need)

    if not jobs:
        raise SystemExit("没有匹配到任何字片，检查 unicode-range 解析")

    def dl(item):
        fname, _r, _w = item
        dest = OUT / fname
        if dest.exists() and not force:
            return fname, dest.stat().st_size, True
        r = httpx.get(f"{CDN}/files/{fname}", timeout=40, follow_redirects=True)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return fname, len(r.content), False

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(dl, jobs))

    total = sum(sz for _, sz, _ in results)
    cached = sum(1 for _, _, c in results if c)
    print(f"  下载 {len(results)} 片（{cached} 片已存在跳过），合计 {total/1024:.0f} KB")

    # 生成 CSS：只写本地确实存在的字片，浏览器就不会去请求缺片
    blocks = []
    for w, css in css_by_weight.items():
        for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
            mw = re.search(r"font-weight:\s*(\d+)", block)
            mf = re.search(r"url\(\./files/([^)]+\.woff2)\)", block)
            if not mw or not mf or int(mw.group(1)) != w:
                continue
            if not (OUT / mf.group(1)).exists():
                continue
            ur = re.search(r"unicode-range:\s*([^;}]+)", block)
            blocks.append(
                "@font-face{font-family:'%s';font-style:normal;font-display:swap;"
                "font-weight:%s;src:url(/static/fonts/%s) format('woff2');"
                "unicode-range:%s}" % (FAMILY, mw.group(1), mf.group(1),
                                       (ur.group(1).strip() if ur else "U+0-10FFFF")))
    CSS_OUT.parent.mkdir(parents=True, exist_ok=True)
    CSS_OUT.write_text("\n".join(blocks) + "\n", "utf-8")
    print(f"  写出 {CSS_OUT}（{len(blocks)} 条 @font-face）")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
