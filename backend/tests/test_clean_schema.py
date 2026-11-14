import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.base_model import MappedBase
from app.modules.ai.chat import crud as chat_crud
from app.scripts.initialize import InitializeData
from app.utils.import_util import ImportUtil


def test_initial_schema_matches_models_and_contains_no_retired_fields():
    ImportUtil.find_models(MappedBase)
    metadata = sa.MetaData()
    for mapper in MappedBase.registry.mappers:
        if mapper.class_.__module__.startswith("app.modules."):
            mapper.local_table.to_metadata(metadata)
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_14_1400_argus_initial.py"
    spec = importlib.util.spec_from_file_location("argus_initial", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision is None
    assert len(list(path.parent.glob("*.py"))) == 2
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names()) == set(metadata.tables)
        assert len(inspector.get_table_names()) == 22
        for table, removed in {
            "sys_user": {"gitee_login", "github_login", "wx_login", "qq_login"},
            "sys_ticket": {"images", "reply"},
            "task_storage_node": {"path_prefix"},
        }.items():
            assert not removed & {column["name"] for column in inspector.get_columns(table)}
        assert "sys_position" in inspector.get_table_names()
        assert "sys_task_notification" in inspector.get_table_names()
        assert not compare_metadata(MigrationContext.configure(connection), metadata)
        migration.downgrade()
        assert sa.inspect(connection).get_table_names() == []
    engine.dispose()


async def test_startup_runs_only_explicit_migrations(monkeypatch):
    calls = []
    monkeypatch.setattr("alembic.command.upgrade", lambda config, target: calls.append(target))
    monkeypatch.setattr("alembic.command.stamp", lambda *args, **kwargs: pytest.fail("startup must not stamp"))
    monkeypatch.setattr("alembic.command.revision", lambda *args, **kwargs: pytest.fail("startup must not generate migrations"))
    await InitializeData._InitializeData__apply_migrations()
    assert calls == ["head"]


async def test_chat_initializes_only_session_and_schema_version_tables(monkeypatch):
    database = type("Database", (), {"_get_table": AsyncMock()})()
    monkeypatch.setattr(chat_crud, "_get_agno_db", lambda: database)
    await chat_crud.init_agno_tables()
    assert database._get_table.call_args_list == [
        ((), {"table_type": "versions", "create_table_if_not_found": True}),
        ((), {"table_type": "sessions", "create_table_if_not_found": True}),
    ]


async def test_default_user_permissions_exclude_administration():
    import json
    from types import SimpleNamespace
    from unittest.mock import Mock

    menus = []

    def flatten(items, parent_id=None):
        for item in items:
            menu = SimpleNamespace(id=len(menus) + 1, parent_id=parent_id,
                                   route_name=item.get("route_name"), permission=item.get("permission"))
            menus.append(menu)
            flatten(item.get("children", []), menu.id)

    flatten(json.loads((Path(__file__).parents[1] / "sql/sys_menu.json").read_text()))
    roles = [SimpleNamespace(id=1, code="USER"), SimpleNamespace(id=2, code="ADMIN")]
    db = SimpleNamespace(scalars=AsyncMock(side_effect=[SimpleNamespace(all=lambda: menus),
                                                       SimpleNamespace(all=lambda: roles)]),
                         add_all=Mock(), flush=AsyncMock())
    await InitializeData._InitializeData__init_role_permissions(db)
    grants = [list(call.args[0]) for call in db.add_all.call_args_list]
    user_ids = {grant.menu_id for grant in grants[0]}
    permissions = {menu.permission for menu in menus if menu.id in user_ids}
    assert {"module_ai:knowledge:query", "module_system:ticket:create",
            "module_task:storage:browse:upload"} <= permissions
    assert "module_task:storage:node:manage" not in permissions
    elevated = {"module_task:storage:browse:department_manage", "module_task:storage:browse:manage_all"}
    for group in grants:
        assert not {menu.permission for menu in menus if menu.id in {g.menu_id for g in group}} & elevated
    for menu in menus:
        if menu.id in user_ids and menu.parent_id and menu.route_name:
            assert menu.parent_id in user_ids
