from app.classify import (NOTICE_INFO, NOTICE_OPENING, NOTICE_RESULT, infer_city,
                          infer_job_type, infer_notice_kind)


def test_job_type():
    assert infer_job_type("律师事务所招聘实习律师") == "intern"
    assert infer_job_type("广州市中级人民法院聘用制书记员招聘") == "public"
    assert infer_job_type("某公司法务专员") == "legal_counsel"
    assert infer_job_type("广东华商律师事务所招聘执业律师") == "lawfirm"
    assert infer_job_type("普通岗位") == "unknown"


def test_city():
    assert infer_city("深圳市福田区人民法院招聘") == "深圳"
    assert infer_city("珠三角某岗位", default="广州") == "广州"
    assert infer_city("无城市信息") is None


def test_notice_kind_opening():
    for t in ["广东省事业单位2026年集中公开招聘高校毕业生公告",
              "佛山市第一人民医院2026年公开招聘公告",
              "广东外语外贸大学2026年招聘工作人员公告",
              "2026年度珠海市市本级高校毕业生基层公共就业创业服务岗位招募公告"]:
        assert infer_notice_kind(t) == NOTICE_OPENING, t


def test_notice_kind_result():
    for t in ["中山市人民政府南区街道办事处所属事业单位2025年第二期公开招聘拟聘用人员名单公示",
              "关于广东省事业单位2026年集中公开招聘高校毕业生省直及中央驻粤单位笔试合格分数线的公告",
              "广东省高级人民法院2026年度选调优秀大学毕业生拟录用人员名单公示",
              "中共珠海市委党校2026年招聘教师拟聘人员公示"]:
        assert infer_notice_kind(t) == NOTICE_RESULT, t


def test_result_wins_over_recruit_in_body():
    """标题是公示、正文里出现"公开招聘公告规定"时，仍应判为结果类。"""
    body = "根据《…事业单位2026年公开招聘人员公告》规定，经报名、资格审查、考试…现予以公示。"
    assert infer_notice_kind("…拟聘用人员名单公示", body) == NOTICE_RESULT


def test_notice_kind_info():
    assert infer_notice_kind("关于电子诉讼服务整合升级的公告") == NOTICE_INFO
    assert infer_notice_kind("关于征集2026年专题研讨会论文的通知") == NOTICE_INFO
