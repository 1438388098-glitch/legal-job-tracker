"""正文快照 → 结构化展示。

快照文件存的是详情页抽取的纯文本（每源格式不一），直接塞进 <pre> 是一坨
没有层级的字。这里把它整理成「关键信息卡 + 带小节标题的正文」：

- 小节标题：公文惯用的 一、二、… / （一）（二）… / 第X部分（短行才认，
  长句以"一、"开头的是正文）
- 关键信息：截止/报名时间、报名方式、学历要求、待遇、联系方式——招聘公告
  里用户最先要找的东西，提到卡片里一眼看到，不用在几千字里滚屏
- 只做行级整理，不做语义理解：认不出的行原样保留，宁可不美化也不能改内容
"""
import re
from html import escape

# 公文小节标题：一、 / （一） / 第一部分 / 一.
_H1 = re.compile(r"^[一二三四五六七八九十]{1,3}\s*[、.．]")
_H2 = re.compile(r"^（[一二三四五六七八九十]{1,3}）")
_H3 = re.compile(r"^第[一二三四五六七八九十]{1,3}(部分|章|节)")

# 关键信息行：用户找公告最先看的就是这些
_KEY = re.compile(
    r"截止|报名(时间|方式|日期|地点)|简历投递|投递方式|招聘(程序|流程)"
    r"|联系(人|电话|方式)|咨询电话|邮箱|网址|二维码"
    r"|学历|本科|硕士|博士|研究生|大专|待遇|薪酬|工资|薪资|五险|报名费")
_TRIM = 160          # 关键信息卡里每行最多展示的字数
_MAX_BLOCKS = 500    # 正文块上限，防超长快照拖垮渲染


def _is_heading(line: str) -> str | None:
    """短行 + 公文编号前缀 → 小节标题。长句开头是'一、'的不算。"""
    if len(line) > 40:
        return None
    if _H1.match(line) or _H2.match(line) or _H3.match(line):
        return "h2" if (_H2.match(line) and not _H1.match(line)) else "h1"
    return None


def _paragraphs(text: str) -> list[str]:
    """连续非空行合并成段（快照里换行可能只是源站排版，不是段落边界）。"""
    paras, buf = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if buf:
                paras.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        paras.append("\n".join(buf))
    return paras


def render_snapshot(text: str) -> dict:
    """纯文本 → {key: [行], html: 安全 HTML}。html 已转义，模板直接 |safe。"""
    blocks: list[tuple[str, str]] = []   # (kind, text)：h1/h2/p
    keys: list[str] = []
    seen_key = set()
    for para in _paragraphs(text or ""):
        for line in para.split("\n"):
            kind = _is_heading(line)
            if kind:
                blocks.append((kind, line))
                continue
            blocks.append(("p", line))
            if _KEY.search(line) and len(keys) < 8 and line not in seen_key:
                seen_key.add(line)
                keys.append(line[:_TRIM] + ("…" if len(line) > _TRIM else ""))
        if len(blocks) >= _MAX_BLOCKS:
            break
    blocks = blocks[:_MAX_BLOCKS]

    parts = []
    for kind, txt in blocks:
        e = escape(txt)
        if kind == "h1":
            parts.append(f"<h4 class='snap-h1'>{e}</h4>")
        elif kind == "h2":
            parts.append(f"<h5 class='snap-h2'>{e}</h5>")
        else:
            parts.append(f"<p>{e}</p>")
    return {"key": keys, "html": "".join(parts)}
