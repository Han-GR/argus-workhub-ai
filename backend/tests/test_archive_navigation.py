import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleModel
from app.modules.task.storage.node.model import StorageNodeModel


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


def test_navigation_migration_preserves_browsing_without_assigning_cross_department_power():
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_14_1300_7a8b9c0d1e23.py"
    spec = importlib.util.spec_from_file_location("archive_navigation", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        for table in (MenuModel.__table__, RoleModel.__table__, StorageNodeModel.__table__):
            table.create(conn)
        conn.execute(sa.text("CREATE TABLE sys_role_menus (role_id INTEGER, menu_id INTEGER, PRIMARY KEY (role_id, menu_id))"))
        menu = MenuModel.__table__
        for id, route, parent, type, permission in [
            (1, "Task", None, 1, None), (2, "Storage", 1, 1, None),
            (3, "WorkflowBrowse", 2, 2, "module_task:storage:browse:query"),
            (4, "WorkflowNode", 2, 2, "module_task:storage:node:query"),
        ]:
            conn.execute(menu.insert().values(id=id, name=route, type=type, order=id,
                route_name=route, parent_id=parent, permission=permission))
        for id, code in [(1, "ADMIN"), (2, "USER")]:
            conn.execute(RoleModel.__table__.insert().values(id=id, name=code, code=code))
            for menu_id in (1, 2, 3, 4):
                conn.execute(sa.text("INSERT INTO sys_role_menus VALUES (:r,:m)"), {"r": id, "m": menu_id})
        conn.execute(StorageNodeModel.__table__.insert().values(name="local", protocol="local", port=0, host="static/upload"))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        assert conn.execute(sa.select(menu.c.id).where(menu.c.route_name == "Storage")).first() is None
        assert conn.execute(sa.select(menu.c.parent_id).where(menu.c.id == 3)).scalar_one() == 1
        for role, expected in [(1, {"module_task:storage:browse:query", "module_task:storage:node:query", "module_task:storage:node:manage"}),
                               (2, {"module_task:storage:browse:query"})]:
            permissions = set(conn.execute(sa.text("SELECT permission FROM sys_menu m JOIN sys_role_menus g ON m.id=g.menu_id WHERE g.role_id=:r AND permission IS NOT NULL"), {"r": role}).scalars())
            assert permissions == expected
        assert conn.execute(sa.select(StorageNodeModel.host)).scalar_one() == "data/archive"
    engine.dispose()
