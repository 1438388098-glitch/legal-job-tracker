import json
from pathlib import Path

from app.collect import zuel


def test_parse_api_payload():
    data = json.loads(Path("tests/fixtures/zuel_api.json").read_text("utf-8"))
    items = zuel.parse_payload(data, "https://jyzx.zuel.edu.cn")
    assert items, "至少解析出一条"
    it = items[0]
    assert it["title"]
    assert it["url"].startswith("https://jyzx.zuel.edu.cn")
    assert it["job_type"] in {"intern", "lawfirm", "public", "legal_counsel", "unknown"}
    assert it["org"]
