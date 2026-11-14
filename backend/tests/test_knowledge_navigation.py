import json
from pathlib import Path


def test_knowledge_seed_is_a_directory_with_two_independent_pages():
    root = Path(__file__).parents[2]
    menus = json.loads((root / "backend/sql/sys_menu.json").read_text())
    knowledge = next(menu for menu in menus if menu.get("route_name") == "Knowledge")
    assert knowledge["type"] == 1 and knowledge["component_path"] is None
    assert knowledge["redirect"] == "/knowledge/documents"
    assert [child["name"] for child in knowledge["children"]] == ["文档管理", "知识问答"]
    for child in knowledge["children"]:
        assert child["permission"] == "module_ai:knowledge:query"
        assert (root / "frontend/web/src/views" / f"{child['component_path']}.vue").is_file()
