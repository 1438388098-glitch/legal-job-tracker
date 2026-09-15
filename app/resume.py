"""简历解析 → 个人画像 → 岗位匹配。

设计上刻意不做"机器学习"：这是单机工具，简历只有一份，训练/推理都不划算。
用规则抽取 + 加权打分，好处是**每一分都能解释**——推荐理由里能明确说出
"因为你意向广州 + 岗位命中法务 + 你有律所实习经历"，用户能判断该不该信。

抽取失败不报错，返回空字段让用户手填：宁可画像不完整，也不能给出自信的错误。
"""
import json
import re

from .classify import CITIES, LAW_KEYWORDS

# ── 学历 ──────────────────────────────────────────────────────────────────
DEGREES = [("博士", 4), ("硕士", 3), ("研究生", 3), ("本科", 2), ("学士", 2),
           ("专科", 1), ("大专", 1)]
_SCHOOL = re.compile(r"([\u4e00-\u9fa5]{2,12}(?:大学|学院|学校|政法大学|财经大学))")
_MAJOR = re.compile(r"(?:专业|主修)[:：\s]*([\u4e00-\u9fa5]{2,12})")
_MAJOR_BARE = re.compile(r"(法学|法律|知识产权|社会学|行政管理|金融学|会计学|汉语言文学"
                         r"|侦查学|治安学|国际经济与贸易)")

# ── 经历 ──────────────────────────────────────────────────────────────────
# 法学求职者的经历类型直接决定匹配哪类岗位，权重给得比技能高
_EXP_PAT = [
    ("法院", re.compile(r"法院|审判|书记员|法官助理")),
    ("检察院", re.compile(r"检察院|检察|公诉|检察官助理")),
    ("律所", re.compile(r"律师事务所|律所|实习律师|律师助理|授薪律师|合伙人")),
    ("法务", re.compile(r"法务|合规|法律顾问|合同管理|风控")),
    ("公安", re.compile(r"公安局|派出所|交警|刑侦|治安")),
    ("仲裁", re.compile(r"仲裁委|仲裁委员会|仲裁员")),
    ("公证", re.compile(r"公证处|公证员")),
    ("公务员", re.compile(r"公务员|选调生|事业单位|街道办|镇政府")),
]
_PERIOD = re.compile(r"(20\d{2})\s*[.\-/年]\s*(\d{1,2})?\s*月?\s*[-–—~至到]\s*"
                     r"(20\d{2}|至今|现在|今)\s*[.\-/年]?\s*(\d{1,2})?")

# ── 技能 ──────────────────────────────────────────────────────────────────
# 按"法学求职者简历上真会写的东西"列，不追求大而全
SKILL_WORDS = [
    "法律检索", "法律文书", "合同审查", "合同起草", "尽职调查", "诉讼", "仲裁",
    "民法典", "刑法", "行政法", "公司法", "劳动法", "知识产权", "合同法", "商法",
    "民事诉讼法", "刑事诉讼法", "法律英语", "合规风控", "谈判", "尽职调查",
    "法律研究", "案例分析", "公文写作", "调解", "公证", "司法鉴定",
    "通过法律职业资格考试", "法律职业资格", "法考", "A证", "CET-6", "雅思",
]
# 通用技能（非法律但常用于匹配企业法务岗）
GENERAL_WORDS = ["团队协作", "沟通", "项目管理", "数据分析", "英语", "Office",
                 "Excel", "PPT", "公文", "写作"]


def extract_text(filename: str, data: bytes) -> str:
    """从上传文件里取纯文本。pdf/docx 需要可选依赖，缺失时给出明确提示。"""
    low = (filename or "").lower()
    if low.endswith((".txt", ".md", ".markdown")):
        for enc in ("utf-8", "gb18030", "utf-16"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
    if low.endswith(".docx"):
        import io

        import docx
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if low.endswith(".pdf"):
        import io

        import pypdf
        r = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    # 其余按纯文本试（.doc 老格式无法解析，会落到乱码兜底）
    return data.decode("utf-8", errors="replace")


# 简历的小节标题。按小节切分是必要的：不切的话会把"教育经历 2020-2024"当成
# 工作年限（实测算出"4 年工作经验"的应届生），也会把求职意向里的"法务"当成
# 实际经历。经历只能从实习/工作段落里读。
_SEC = re.compile(
    r"^\s*(教育背景|教育经历|学习经历|学历|实习经历|实习|工作经历|工作经验|"
    r"项目经历|社会实践|校园经历|学生工作|技能|专业技能|证书|荣誉|获奖|"
    r"自我评价|求职意向|期望|基本信息)[:：]?\s*$", re.M)
_EDU_SEC = ("教育背景", "教育经历", "学习经历", "学历")
_EXP_SEC = ("实习经历", "实习", "工作经历", "工作经验", "项目经历", "社会实践",
            "校园经历", "学生工作")


def _sections(t: str) -> dict[str, str]:
    """把简历切成 {小节名: 正文}。没有小节时整篇归到 ''。"""
    marks = [(m.start(), m.group(1)) for m in _SEC.finditer(t)]
    if not marks:
        return {"": t}
    out = {}
    if marks[0][0] > 0:
        out[""] = t[:marks[0][0]]
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        out[name] = out.get(name, "") + t[pos:end]
    return out


def parse_resume(text: str) -> dict:
    """从简历正文抽取画像字段。抽不到就留空，不猜。"""
    t = re.sub(r"[ \t]+", " ", text or "")
    secs = _sections(t)
    edu_text = " ".join(v for k, v in secs.items() if k in _EDU_SEC) or t
    exp_text = " ".join(v for k, v in secs.items() if k in _EXP_SEC)
    out: dict = {"education": [], "skills": [], "experiences": [],
                 "cities": [], "job_types": [], "years": None, "name": ""}

    # 姓名：取开头第一行里 2-4 个汉字且不是学校/标题的短串
    for line in t.splitlines()[:8]:
        line = line.strip()
        if 2 <= len(line) <= 4 and re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", line):
            if not any(w in line for w in ("简历", "个人", "求职", "应聘", "姓名")):
                out["name"] = line
                break

    # 学历：只在教育段里找（全文兜底会误读求职意向里的"本科以上"等表述）
    for deg, level in DEGREES:
        if deg in edu_text:
            edu = {"degree": deg, "level": level, "school": None, "major": None,
                   "year": None}
            m = _MAJOR.search(edu_text)
            if m:
                edu["major"] = m.group(1)
            else:
                mb = _MAJOR_BARE.search(edu_text)
                if mb:
                    edu["major"] = mb.group(1)
            for m in _SCHOOL.finditer(edu_text):
                edu["school"] = m.group(1)
                if level >= 3:      # 本科以上，靠后出现的通常是最高学历
                    break
            y = re.search(rf"(20\d{{2}})\s*[.\-/年]?\s*(?:{deg}|毕业|入学)", edu_text)
            if y:
                edu["year"] = y.group(1)
            out["education"].append(edu)
            break
    # 学校单独兜底（简历里可能只写学校不写"本科"）
    if not out["education"]:
        m = _SCHOOL.search(edu_text)
        mb = _MAJOR_BARE.search(edu_text)
        if m:
            out["education"].append({"degree": "", "level": 0, "school": m.group(1),
                                     "major": mb.group(1) if mb else None, "year": None})

    # 经历：只认实习/工作段落。求职意向里写的"法务专员"不算经历。
    src = exp_text or t
    for kind, pat in _EXP_PAT:
        if pat.search(src):
            out["experiences"].append({"kind": kind, "detail": ""})
    # 年限：只从经历段的时间跨度粗算（教育段的 2020-2024 是学制不是工龄）
    spans = _PERIOD.findall(exp_text)
    if spans:
        years = []
        for a, _, b, _ in spans:
            try:
                y0 = int(a)
                y1 = 2026 if b in ("至今", "现在", "今") else int(b)
                if 1980 <= y0 <= y1 <= 2100:
                    years.append(y1 - y0)
            except ValueError:
                continue
        # 实习通常只有几个月，按年算会得 0，取最大跨度即可
        out["years"] = max(years) if years else 0
    elif exp_text:
        out["years"] = 0

    # 技能：命中词表才收，避免把整段话塞进来
    found = [w for w in SKILL_WORDS if w in t]
    found += [w for w in GENERAL_WORDS if w in t]
    out["skills"] = list(dict.fromkeys(found))

    # 意向城市：简历里出现的广东城市（出现即视为可接受，后续可手改）
    out["cities"] = [c for c in CITIES if c in t]

    # 意向岗位类型：从经历类型与个人陈述推断
    jt = set()
    for e in out["experiences"]:
        if e["kind"] in ("法院", "检察院", "公务员", "公安", "仲裁", "公证"):
            jt.add("public")
        elif e["kind"] == "律所":
            jt.add("lawfirm")
        elif e["kind"] == "法务":
            jt.add("legal_counsel")
    if "实习" in t:
        jt.add("intern")
    out["job_types"] = sorted(jt)
    return out


def profile_keywords(profile: dict) -> list[str]:
    """画像 → 用于匹配岗位的检索词。

    画像的"技能/经历"才是信号，姓名学校这些对匹配没用，不能混进来。
    """
    words = list(profile.get("skills") or [])
    for e in profile.get("experiences") or []:
        if e.get("kind"):
            words.append(e["kind"])
    words += [k for k in LAW_KEYWORDS if k in (profile.get("raw_text") or "")]
    return list(dict.fromkeys(w for w in words if w))


# ── 匹配打分 ──────────────────────────────────────────────────────────────
# 每一项都返回 (得分, 理由)，页面直接展示理由——用户要能判断推荐是否靠谱
W_CITY = 26
W_TYPE = 22
W_SKILL = 8        # 每个专业词
W_SKILL_WEAK = 3   # 每个泛词（"法律""合同"这类，命中太容易，给多了会让分数饱和）
W_SKILL_CAP = 24
W_EXP = 14
W_EDU = 8
W_DEADLINE = 6     # 还来得及投的优先
# 上面各项满分正好 100，不设基线分：加了基线后前几十条全是 100，区分度归零，
# 用户看不出该先投哪个
WEAK_WORDS = {"法律", "法学", "合同", "英语", "Office", "写作", "律师", "法院",
              "法务", "合规", "法院"}


def match_job(profile: dict, job: dict, keywords: list[str] | None = None) -> dict:
    """给单个岗位打分。返回 {score, reasons, hits}。"""
    keywords = keywords if keywords is not None else profile_keywords(profile)
    reasons: list[str] = []
    hits: list[str] = []
    score = 0

    haystack = f"{job.get('title') or ''} {job.get('org') or ''} " \
               f"{job.get('city') or ''} {job.get('search_text') or ''}"

    # 城市
    cities = profile.get("cities") or []
    job_city = job.get("city") or ""
    if cities and job_city:
        if any(c in job_city or job_city in c for c in cities):
            score += W_CITY
            reasons.append(f"意向城市 {job_city}")
        else:
            score -= W_CITY // 2
            reasons.append(f"城市不符（你要 {cities[0]}，岗位在 {job_city}）")

    # 岗位类型
    jts = profile.get("job_types") or []
    jt = job.get("job_type")
    if jts and jt in jts:
        score += W_TYPE
        reasons.append(f"匹配你的{_jt_label(jt)}方向")
    elif jts:
        score -= 4

    # 技能/经历关键词命中：泛词给低分，否则"正文里出现过法律二字"就能顶满
    for w in keywords:
        if w and w in haystack:
            hits.append(w)
    if hits:
        add = min(sum(W_SKILL_WEAK if w in WEAK_WORDS else W_SKILL for w in hits),
                  W_SKILL_CAP)
        score += add
        strong = [w for w in hits if w not in WEAK_WORDS]
        shown = strong or hits
        reasons.append("命中 " + "、".join(shown[:4])
                       + (f" 等 {len(shown)} 项" if len(shown) > 4 else ""))

    # 经历类型与岗位类型一致（比关键词更强）
    exp_kinds = {e.get("kind") for e in (profile.get("experiences") or [])}
    if exp_kinds and jt:
        pair = {"lawfirm": "律所", "public": "法院", "legal_counsel": "法务"}
        want = pair.get(jt)
        if want and want in exp_kinds:
            score += W_EXP
            reasons.append(f"你有{want}经历")

    # 学历：岗位正文提到要求学历且画像更高/相等
    edu = (profile.get("education") or [{}])[0]
    if edu.get("level"):
        m = re.search(r"(博士|硕士|研究生|本科|大专|专科)", job.get("search_text") or "")
        if m:
            need = dict(DEGREES).get(m.group(1), 2)
            if edu["level"] >= need:
                score += W_EDU
                reasons.append(f"学历满足（{m.group(1)}及以上）")

    # 临期加分：还投得上的优先（已过期的直接不进推荐）
    if job.get("deadline"):
        score += W_DEADLINE
        reasons.append("已明确截止日期")

    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons[:5], "hits": hits}


def _jt_label(jt: str) -> str:
    return {"lawfirm": "律所", "public": "体制内", "legal_counsel": "法务",
            "intern": "实习"}.get(jt, jt)


def load_profile(conn) -> dict | None:
    row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if row is None:
        return None
    p = dict(row)
    for k in ("education", "skills", "experiences", "cities", "job_types", "keywords"):
        try:
            p[k] = json.loads(p[k] or "[]")
        except (ValueError, TypeError):
            p[k] = []
    return p


def save_profile(conn, data: dict) -> None:
    prof = {
        "name": data.get("name", ""),
        "education": data.get("education") or [],
        "skills": data.get("skills") or [],
        "experiences": data.get("experiences") or [],
        "cities": data.get("cities") or [],
        "job_types": data.get("job_types") or [],
        "years": data.get("years"),
        "raw_text": data.get("raw_text", ""),
        "source_file": data.get("source_file", ""),
    }
    prof["keywords"] = profile_keywords(prof)
    conn.execute(
        "INSERT INTO profile(id,name,education,skills,experiences,cities,job_types,"
        "keywords,years,raw_text,source_file,updated_at) "
        "VALUES(1,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime')) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, education=excluded.education, "
        "skills=excluded.skills, experiences=excluded.experiences, cities=excluded.cities, "
        "job_types=excluded.job_types, keywords=excluded.keywords, years=excluded.years, "
        "raw_text=excluded.raw_text, source_file=excluded.source_file, "
        "updated_at=datetime('now','localtime')",
        (prof["name"], json.dumps(prof["education"], ensure_ascii=False),
         json.dumps(prof["skills"], ensure_ascii=False),
         json.dumps(prof["experiences"], ensure_ascii=False),
         json.dumps(prof["cities"], ensure_ascii=False),
         json.dumps(prof["job_types"], ensure_ascii=False),
         json.dumps(prof["keywords"], ensure_ascii=False),
         prof["years"], prof["raw_text"], prof["source_file"]))
    conn.commit()
