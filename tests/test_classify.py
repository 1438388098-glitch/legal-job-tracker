from app.classify import (NOTICE_INFO, NOTICE_OPENING, NOTICE_RESULT, extract_org,
                          infer_city, infer_job_type, infer_notice_kind)


def test_job_type():
    assert infer_job_type("律师事务所招聘实习律师") == "intern"
    assert infer_job_type("广州市中级人民法院聘用制书记员招聘") == "public"
    assert infer_job_type("某公司法务专员") == "legal_counsel"
    assert infer_job_type("广东华商律师事务所招聘执业律师") == "lawfirm"
    assert infer_job_type("普通岗位") == "unknown"


def test_job_type_covers_public_sector_variants():
    """人社厅栏目里的常见写法都得认出来，否则会成片落进"未分类"。

    这是实测出来的问题：原词表只有"法院|事业单位|…"，而人社厅的标题几乎都是
    "某某大学/医院 公开招聘工作人员公告"，一个词都命中不了。
    """
    for t in ["广州中医药大学第三附属医院2026年第一批公开招聘工作人员公告",
              "佛山大学2026年第二批辅导员招聘公告",
              "广州职业技术大学2026年上半年引进急需人才公告",
              "佛山高新技术产业开发区管理委员会公开招聘工作人员公告",
              "广东省人民检察院2026年考试录用公务员公告",
              "深圳市龙岗区平湖街道办事处公开招聘社区工作者公告"]:
        assert infer_job_type(t) == "public", t


def test_city():
    assert infer_city("深圳市福田区人民法院招聘") == "深圳"
    assert infer_city("珠三角某岗位", default="广州") == "广州"
    assert infer_city("无城市信息") is None


def test_extract_org_from_title():
    """政务站列表页没有单位字段，单位名只能从标题抽。"""
    cases = {
        "广东省高级人民法院2026年度选调优秀大学毕业生拟录用人员名单公示":
            "广东省高级人民法院",
        "广州中医药大学第三附属医院2026年第一批公开招聘工作人员公告":
            "广州中医药大学第三附属医院",
        "广东检察官（培训）学院集中公开招聘面试公告":
            "广东检察官（培训）学院",
        "广东省高级人民法院劳动合同制书记员招聘公告":
            "广东省高级人民法院",
        "市人力资源保障局关于转发深圳科学高中2026年3月公开选聘教师拟聘人员公示":
            "市人力资源保障局",
        "佛山高新技术产业开发区管理委员会公开招聘工作人员公告":
            "佛山高新技术产业开发区管理委员会",
        "2025年度广东检察官（培训）学院集中公开招聘面试公告":
            "广东检察官（培训）学院",
        "厦门国际银行股份有限公司": "厦门国际银行股份有限公司",
    }
    for title, want in cases.items():
        assert extract_org(title) == want, f"{title} → {extract_org(title)!r}，期望 {want!r}"


def test_extract_org_refuses_to_guess():
    """抽不到就返回 None —— 显示半句话当单位名比空着更糟。"""
    assert extract_org("关于召开公开听证会的公告") is None
    assert extract_org("关于开展2026年度考核工作的通知") is None
    assert extract_org("公告") is None
    assert extract_org("") is None


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
              "中共珠海市委党校2026年招聘教师拟聘人员公示",
              "广东省高级人民法院劳动合同制书记员招聘有关人选名单公示"]:
        assert infer_notice_kind(t) == NOTICE_RESULT, t


def test_result_wins_over_recruit_in_body():
    """标题是公示、正文里出现"公开招聘公告规定"时，仍应判为结果类。"""
    body = "根据《…事业单位2026年公开招聘人员公告》规定，经报名、资格审查、考试…现予以公示。"
    assert infer_notice_kind("…拟聘用人员名单公示", body) == NOTICE_RESULT


def test_notice_kind_info():
    assert infer_notice_kind("关于电子诉讼服务整合升级的公告") == NOTICE_INFO
    assert infer_notice_kind("关于征集2026年专题研讨会论文的通知") == NOTICE_INFO


def test_procurement_notice_is_not_a_job():
    """采购/询价类稿件常带"招聘活动"字样，但是给供应商看的，不是岗位。"""
    assert infer_notice_kind(
        "关于落实省“百万英才汇南粤”2026年N城联动秋季招聘活动发动及参展项目公开询价公告"
    ) == NOTICE_INFO
    assert infer_notice_kind("某单位招聘会服务项目中标公告") == NOTICE_INFO
