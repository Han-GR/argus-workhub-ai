import json
from pathlib import Path
from app.modules.system.user.service import UserService


def test_management_entries_need_write_permissions():
    show = UserService._can_show_management_menu
    assert not show("Params", set())
    assert not show("WorkflowNode", {"module_task:storage:node:query"})
    assert show("Params", {"module_system:param:update"})
    assert show("WorkflowNode", {"module_task:storage:node:update"})
    assert show("WorkflowBrowse", set())


def test_management_menu_seeds_are_visible():
    menus = json.loads((Path(__file__).parents[1] / "sql/sys_menu.json").read_text())
    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.get("children") or [])
    entries = {n.get("route_name"): n for n in walk(menus)}
    assert not entries["Params"]["hidden"]
    assert not entries["WorkflowNode"]["hidden"]
    assert entries["WorkflowNode"]["name"] == "存储源管理"


async def test_admin_and_query_only_user_receive_different_menu_visibility(test_client):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config.setting import settings
    from app.core.base_schema import AuthSchema
    from app.modules.system.menu.model import MenuModel

    engine = create_async_engine(settings.ASYNC_DB_URI, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine)() as db:
            rows = (await db.execute(select(MenuModel).where(MenuModel.route_name.in_(["Params", "WorkflowNode", "WorkflowBrowse"])))).scalars().all()
            ids = [row.id for row in rows]
            regular = AuthSchema(user={"id": 1}, menu_ids=ids, permissions=["module_task:storage:node:query"])
            regular_menus = {m.route_name: m for m in await UserService(regular, db)._load_menus()}
            assert regular_menus["Params"].hidden
            assert regular_menus["WorkflowNode"].hidden
            assert not regular_menus["WorkflowBrowse"].hidden
            admin = AuthSchema(user={"id": 1, "is_superuser": True})
            admin_menus = {m.route_name: m for m in await UserService(admin, db)._load_menus()}
            assert not admin_menus["Params"].hidden
            assert not admin_menus["WorkflowNode"].hidden
    finally:
        await engine.dispose()
