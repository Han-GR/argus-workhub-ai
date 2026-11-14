import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.system.menu.model import MenuModel


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


def test_submenu_migration_preserves_existing_role_access_and_is_repeatable():
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_14_1100_5e6f7a8b9c01.py"
    spec = importlib.util.spec_from_file_location("knowledge_navigation", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            MenuModel.__table__.create(conn)
            conn.execute(sa.text("CREATE TABLE sys_role_menus (role_id INTEGER, menu_id INTEGER, PRIMARY KEY (role_id, menu_id))"))
            menu = MenuModel.__table__
            root_id = conn.execute(menu.insert().values(name="知识库", title="知识库", type=2, order=25,
                route_name="Knowledge", route_path="/knowledge", component_path="module_ai/knowledge/index",
                permission="module_ai:knowledge:query")).inserted_primary_key[0]
            conn.execute(sa.text("INSERT INTO sys_role_menus VALUES (1, :id)"), {"id": root_id})
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            migration.upgrade()
            parent = conn.execute(sa.select(menu).where(menu.c.id == root_id)).mappings().one()
            assert parent["type"] == 1 and parent["component_path"] is None and parent["permission"] is None
            assert parent["redirect"] == "/knowledge/documents"
            children = conn.execute(sa.select(menu).where(menu.c.parent_id == root_id).order_by(menu.c.order)).mappings().all()
            assert [child["route_name"] for child in children] == ["KnowledgeDocuments", "KnowledgeQuestion"]
            assert all(child["permission"] == "module_ai:knowledge:query" for child in children)
            assigned = conn.execute(sa.text("SELECT menu_id FROM sys_role_menus WHERE role_id=1")).scalars().all()
            assert set(assigned) == {root_id, *(child["id"] for child in children)}
            assert conn.execute(sa.text("SELECT COUNT(*) FROM sys_role_menus WHERE role_id=2")).scalar() == 0
    finally:
        engine.dispose()
