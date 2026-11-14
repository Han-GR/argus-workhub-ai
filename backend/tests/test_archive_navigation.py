import json
from pathlib import Path


def test_seed_flattens_archive_menu_and_keeps_management_explicit():
    root = Path(__file__).parents[2]
    menus = json.loads((root / "backend/sql/sys_menu.json").read_text())
    archive = next(m for m in menus if m.get("route_name") == "Task")
    assert [m["name"] for m in archive["children"]] == ["文件管理", "存储源管理"]
    for page in archive["children"]:
        assert page["route_path"].startswith("/task/storage/")
    permissions = {m["permission"] for page in archive["children"] for m in page["children"]}
    assert {"module_task:storage:browse:department_manage", "module_task:storage:browse:manage_all",
            "module_task:storage:node:manage"} <= permissions
    source = json.loads((root / "backend/sql/task_storage_node.json").read_text())[0]
    assert source["host"] == "data/archive"
