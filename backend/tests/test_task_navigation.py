import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.system.menu.model import MenuModel


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


def test_migration_keeps_task_permissions_and_does_not_give_readers_create_access():
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_14_1200_6f7a8b9c0d12.py"
    spec = importlib.util.spec_from_file_location("task_navigation", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        MenuModel.__table__.create(conn)
        conn.execute(sa.text("CREATE TABLE sys_role_menus (role_id INTEGER, menu_id INTEGER, PRIMARY KEY (role_id, menu_id))"))
        menu = MenuModel.__table__
        task_id = conn.execute(menu.insert().values(name="任务协同", type=2, order=20,
            route_name="ModuleTicket", route_path="/system/ticket", permission="module_system:ticket:query")).inserted_primary_key[0]
        create_id = conn.execute(menu.insert().values(name="新增", type=3, order=1,
            parent_id=task_id, permission="module_system:ticket:create")).inserted_primary_key[0]
        conn.execute(sa.text("INSERT INTO sys_role_menus VALUES (1, :task), (1, :create), (2, :task)"), {"task": task_id, "create": create_id})
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        parent_id = conn.execute(sa.select(menu.c.id).where(menu.c.route_name == "TaskCollaboration")).scalar_one()
        meeting_id = conn.execute(sa.select(menu.c.id).where(menu.c.route_name == "MeetingMinutes")).scalar_one()
        task = conn.execute(sa.select(menu).where(menu.c.id == task_id)).mappings().one()
        assert task["parent_id"] == parent_id and task["route_path"] == "/system/ticket"
        for role, expected in [(1, {task_id, create_id, parent_id, meeting_id}), (2, {task_id, parent_id})]:
            assert set(conn.execute(sa.text("SELECT menu_id FROM sys_role_menus WHERE role_id=:role"), {"role": role}).scalars()) == expected
        migration.downgrade()
        assert conn.execute(sa.select(menu.c.parent_id).where(menu.c.id == task_id)).scalar_one() is None
    engine.dispose()
