from app import resume

CV = """陈晓岚
求职意向：法务专员 / 律师助理（广州、深圳）

教育经历
2020.09 - 2024.06  广东外语外贸大学  本科  法学
主修：法学   通过法律职业资格考试（A证）

实习经历
2023.07 - 2023.10  广东广信君达律师事务所  律师助理
  - 协助起草、审查民商事合同 40 余份
2022.07 - 2022.09  广州市天河区人民法院  实习书记员
  - 参与庭审记录、卷宗归档

技能
法律检索、合同审查、尽职调查、法律英语
"""


def test_parse_education_and_name():
    p = resume.parse_resume(CV)
    assert p["name"] == "陈晓岚"
    edu = p["education"][0]
    assert edu["degree"] == "本科" and edu["level"] == 2
    assert "广东外语外贸大学" in edu["school"]
    assert edu["major"] == "法学"


def test_years_not_from_education():
    """年限不能把学制当工龄：这份简历 2020-2024 上学 + 两段实习，应为应届。

    曾经从全文找时间段，算出"4 年工作经验"的应届生——推荐结果随之全错。
    """
    assert resume.parse_resume(CV)["years"] == 0


def test_experience_only_from_work_sections():
    """求职意向里写的"法务专员"不算经历，只有实习/工作段落才算。"""
    kinds = [e["kind"] for e in resume.parse_resume(CV)["experiences"]]
    assert "律所" in kinds and "法院" in kinds
    assert "法务" not in kinds


def test_parse_skills_and_cities():
    p = resume.parse_resume(CV)
    assert "合同审查" in p["skills"]
    assert {"广州", "深圳"}.issubset(set(p["cities"]))


def test_empty_resume_is_safe():
    p = resume.parse_resume("")
    assert p["education"] == [] and p["years"] is None


def test_match_prefers_city_and_type():
    prof = {"cities": ["广州"], "job_types": ["lawfirm"], "skills": ["合同审查"],
            "experiences": [{"kind": "律所"}], "education": [{"level": 2}],
            "raw_text": ""}
    good = {"title": "广东某律师事务所招聘律师助理", "org": "广东某律师事务所",
            "city": "广州", "job_type": "lawfirm", "search_text": "需会合同审查",
            "deadline": "2026-10-01"}
    bad = {"title": "深圳某科技公司招聘", "org": "深圳某科技公司", "city": "深圳",
           "job_type": "unknown", "search_text": "无", "deadline": None}
    a = resume.match_job(prof, good)
    b = resume.match_job(prof, bad)
    assert a["score"] > b["score"]
    assert a["score"] <= 100 and b["score"] >= 0
    assert any("意向城市" in r for r in a["reasons"])
    assert any("命中" in r for r in a["reasons"])
    assert any("城市不符" in r for r in b["reasons"])


def test_profile_roundtrip(conn):
    resume.save_profile(conn, {
        "name": "测试", "skills": ["合同审查"], "cities": ["广州"],
        "job_types": ["lawfirm"], "experiences": [{"kind": "律所"}],
        "education": [{"degree": "本科", "level": 2}], "years": 1,
        "raw_text": "合同审查", "source_file": "cv.txt"})
    p = resume.load_profile(conn)
    assert p["name"] == "测试"
    assert p["skills"] == ["合同审查"]
    # 关键词由画像派生，必须包含技能与经历
    assert "合同审查" in p["keywords"] and "律所" in p["keywords"]
    # 单用户：重复保存是更新而不是插第二行
    resume.save_profile(conn, {"name": "改名", "skills": [], "cities": [],
                               "job_types": [], "experiences": [], "education": [],
                               "years": None, "raw_text": "", "source_file": ""})
    assert conn.execute("SELECT COUNT(*) c FROM profile").fetchone()["c"] == 1
    assert resume.load_profile(conn)["name"] == "改名"


def test_extract_text_txt():
    assert resume.extract_text("a.txt", "你好".encode("utf-8")) == "你好"
    assert "你好" in resume.extract_text("a.txt", "你好".encode("gb18030"))
