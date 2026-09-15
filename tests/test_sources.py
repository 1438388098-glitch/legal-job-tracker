import json
from pathlib import Path

import pytest

from app.collect import generic_html
from scripts.seed_sources import SOURCES

BY_SLUG = {s["slug"]: s for s in SOURCES}


@pytest.mark.parametrize("slug", [s["slug"] for s in SOURCES if s["kind"] == "html"])
def test_list_fixture_parses(slug):
    fx = Path(f"tests/fixtures/{slug}_list.html")
    if not fx.exists():
        pytest.skip(f"{slug} fixture 未录制（源当次不可达，见 source-registry）")
    cfg = BY_SLUG[slug]["config"]
    items = generic_html.parse_list(fx.read_text("utf-8", errors="replace"), cfg)
    assert items, f"{slug}: 列表解析为 0 条，选择器需修正（用 scripts/inspect_page.py 对照）"
    assert all(i["title"] and i["url"].startswith("http") for i in items), \
        f"{slug}: 解析出的条目字段不合法"


def test_zuel_in_seed():
    assert BY_SLUG["zuel"]["kind"] == "zuel"
    assert BY_SLUG["zuel"]["config"]["api"].startswith("https://jyzx.zuel.edu.cn")
