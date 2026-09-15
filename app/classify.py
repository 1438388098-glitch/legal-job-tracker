import re

CITIES = ["广州", "深圳", "珠海", "佛山", "惠州", "东莞", "中山", "江门", "肇庆", "韶关"]

_RULES = [
    ("intern", re.compile(r"实习")),
    ("public", re.compile(r"法院|检察院|公务员|事业单位|书记员|法官助理|检察官助理|招录|警务辅助|审判辅助|国资|国企|编制")),
    ("lawfirm", re.compile(r"律师事务所|律所|执业律师|授薪律师|合伙人|律师助理")),
    ("legal_counsel", re.compile(r"法务|合规|法律顾问|风控")),
]


def infer_job_type(text: str) -> str:
    for key, pat in _RULES:
        if pat.search(text or ""):
            return key
    return "unknown"


def infer_city(text: str, default: str | None = None):
    for c in CITIES:
        if c in (text or ""):
            return c
    return default


# ── 公告性质 ────────────────────────────────────────────────────────────
# 政务渠道里很大一部分稿件不是"开放报名的岗位"，而是事后结果公示
# （拟聘用人员名单公示 / 笔试成绩公告 / 体检考察公告）。实测某批 299 条里
# 这类占近半，且天然没有投递截止日——混在列表里就是用户说的"乱七八糟"。
# 分类后默认隐藏结果类，但保留可搜索（想查"我那次考试结果"时还能找到）。
NOTICE_OPENING = "opening"   # 可投递：招聘公告 / 招考 / 选聘 / 引进
NOTICE_RESULT = "result"     # 事后结果：拟聘公示 / 成绩 / 分数线 / 体检 / 考察
NOTICE_INFO = "info"         # 其他信息类：系统升级、论文征集、办事指南等

_RESULT = re.compile(
    r"拟聘用|拟录用|拟聘人员|聘用人员名单|录用人员名单|拟聘用人选|"
    r"成绩(公告|查询|公布|排名)|合格分数线|笔试合格|面试成绩|总成绩|"
    r"体检(公告|通知|结果)|考察(公告|对象)|拟任|任前公示|公示名单|"
    r"人员名单公示|资格审核(公告|结果)|拟确定|招聘结果")
# 采购/招标类稿件常带"招聘活动"字样但是给供应商看的（如招聘会项目询价），对求职者无用
_NON_JOB = re.compile(
    r"询价|招标|中标|成交(公告|结果)|采购(公告|项目|意向)|比选|竞谈|"
    r"征求意见|意见征集|论文征集|征文|问卷|调查")
_OPENING = re.compile(
    r"招聘|招录|招考|选聘|选调|引进|招募|诚聘|广纳英才|招贤|岗位(表|信息)|公开招聘|公开遴选")


def infer_notice_kind(title: str, body: str = "") -> str:
    """判断稿件性质。标题优先——标题里出现"公示/成绩"基本就是结果类，
    即便正文提到"招聘"（"根据《…公开招聘公告》规定"）也不该当成开放岗位。"""
    t = title or ""
    if _RESULT.search(t):
        return NOTICE_RESULT
    if _NON_JOB.search(t):
        return NOTICE_INFO
    if _OPENING.search(t):
        return NOTICE_OPENING
    # 标题看不出性质时看正文前半段（正文常常大段复述历史流程，只看开头更准）
    head = (body or "")[:600]
    if _RESULT.search(head):
        return NOTICE_RESULT
    if _OPENING.search(head):
        return NOTICE_OPENING
    return NOTICE_INFO
