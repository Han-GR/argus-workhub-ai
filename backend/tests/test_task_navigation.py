import json
from pathlib import Path


def test_task_seed_has_two_pages_and_preserves_task_links():
    root = Path(__file__).parents[2]
    menus = json.loads((root / "backend/sql/sys_menu.json").read_text())
    parent = next(m for m in menus if m.get("route_name") == "TaskCollaboration")
    assert parent["type"] == 1 and parent["component_path"] is None
    task, meeting = parent["children"]
    assert [task["name"], meeting["name"]] == ["我的任务", "会议纪要"]
    assert task["route_path"] == parent["redirect"] == "/system/ticket"
    assert meeting["permission"] == "module_system:ticket:create"
    assert any(m["permission"] == "module_system:ticket:update" for m in task["children"])
    for page in (task, meeting):
        assert (root / "frontend/web/src/views" / f"{page['component_path']}.vue").is_file()
