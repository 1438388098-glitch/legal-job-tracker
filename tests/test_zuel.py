import json
from pathlib import Path

from app.collect import zuel


def _fixture():
    return json.loads(Path("tests/fixtures/zuel_api.json").read_text("utf-8"))


def test_parse_api_payload():
    items = zuel.parse_payload(_fixture(), "https://jyzx.zuel.edu.cn")
    assert items, "至少解析出一条"
    it = items[0]
    assert it["title"]
    assert it["url"].startswith("https://jyzx.zuel.edu.cn")
    assert it["job_type"] in {"intern", "lawfirm", "public", "legal_counsel", "unknown"}
    assert it["org"]
    assert it["notice_kind"] == "opening"


def test_drops_non_legal_roles():
    """岗位名里没有法学角色的记录必须整条丢弃。

    该接口的 majors 会把企业接受的所有专业列全（实测一条列了 38 个，含法学），
    若拿 majors 当过滤依据，"银行""软件工程师"这类泛岗位会全被灌进来。
    """
    items = zuel.parse_payload(_fixture(), "https://jyzx.zuel.edu.cn")
    titles = [i["title"] for i in items]
    assert any("法务专员" in t for t in titles)
    assert any("授薪律师" in t for t in titles)
    assert not any("银行" in t for t in titles), "泛岗位「银行」不应入库"
    assert not any("软件工程师" in t for t in titles), "泛岗位「软件工程师」不应入库"


def test_narrows_multi_position_to_legal_ones():
    """单位本批招 3 个岗位，只保留法学相关的那一个，别把无关岗位列出来。"""
    items = zuel.parse_payload(_fixture(), "https://jyzx.zuel.edu.cn")
    it = next(i for i in items if "中建四局" in i["org"])
    postfix = it["title"].split("｜", 1)[1]     # 单位名本身含"土木"，只查岗位部分
    assert postfix == "法务专员"
    assert "党工团" not in postfix and "工程师" not in postfix
    # 原始岗位列表仍保留在正文里，便于回看这一批还招了什么
    assert "党工团干事" in it["body"]


def test_classifies_by_unit_nature():
    items = zuel.parse_payload(_fixture(), "https://jyzx.zuel.edu.cn")
    firm = next(i for i in items if "律师事务所" in i["org"])
    assert firm["job_type"] == "lawfirm"
