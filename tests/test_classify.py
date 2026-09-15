from app.classify import infer_city, infer_job_type


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
