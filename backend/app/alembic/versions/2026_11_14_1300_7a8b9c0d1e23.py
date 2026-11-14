"""档案菜单压平、管理权限及私有本地存储初始化。"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "7a8b9c0d1e23"
down_revision = "4bf57cc72348"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    menu = sa.Table("sys_menu", metadata, autoload_with=bind)
    grants = sa.Table("sys_role_menus", metadata, autoload_with=bind)
    roles = sa.Table("sys_role", metadata, autoload_with=bind)
    nodes = sa.Table("task_storage_node", metadata, autoload_with=bind)
    now = datetime.now(UTC)
    root = bind.execute(sa.select(menu).where(menu.c.route_name == "Task")).mappings().one_or_none()
    if root:
        storage_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == "Storage")).scalar_one_or_none()
        if storage_id:
            bind.execute(menu.update().where(menu.c.parent_id == storage_id).values(parent_id=root["id"]))
            for role_id in bind.execute(sa.select(grants.c.role_id).where(grants.c.menu_id == storage_id)).scalars():
                if not bind.execute(sa.select(grants).where(grants.c.role_id == role_id, grants.c.menu_id == root["id"])).first():
                    bind.execute(grants.insert().values(role_id=role_id, menu_id=root["id"]))
            bind.execute(grants.delete().where(grants.c.menu_id == storage_id))
            bind.execute(menu.delete().where(menu.c.id == storage_id))
        bind.execute(menu.update().where(menu.c.id == root["id"]).values(always_show=True))
    for route, order, path in [("WorkflowBrowse", 1, "/task/storage/browse"), ("WorkflowNode", 2, "/task/storage/node")]:
        bind.execute(menu.update().where(menu.c.route_name == route).values(order=order, route_path=path))
    for route, name, permission in [
        ("WorkflowBrowse", "部门档案管理", "module_task:storage:browse:department_manage"),
        ("WorkflowBrowse", "跨部门档案管理", "module_task:storage:browse:manage_all"),
        ("WorkflowNode", "存储配置管理", "module_task:storage:node:manage"),
    ]:
        parent_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == route)).scalar_one_or_none()
        if parent_id is None:
            continue
        menu_id = bind.execute(sa.select(menu.c.id).where(menu.c.permission == permission)).scalar_one_or_none()
        if menu_id is None:
            menu_id = bind.execute(menu.insert().values(uuid=str(uuid4()), name=name, title=name, type=3,
                order=10, permission=permission, parent_id=parent_id, status=0, hidden=False, keep_alive=True,
                always_show=False, affix=False, is_iframe=False, is_hide_tab=False, show_badge=False,
                scope="web", is_deleted=False, created_time=now, updated_time=now)).inserted_primary_key[0]
        # 配置管理员不默认取得跨部门文件管理权限。
        if permission == "module_task:storage:node:manage":
            for role_id in bind.execute(sa.select(roles.c.id).where(roles.c.code.in_(["ADMIN", "SUPER_ADMIN"]))).scalars():
                if not bind.execute(sa.select(grants).where(grants.c.role_id == role_id, grants.c.menu_id == menu_id)).first():
                    bind.execute(grants.insert().values(role_id=role_id, menu_id=menu_id))
    user_roles = sa.select(roles.c.id).where(roles.c.code == "USER")
    node_menus = sa.select(menu.c.id).where(menu.c.permission.like("module_task:storage:node:%"))
    bind.execute(grants.delete().where(grants.c.role_id.in_(user_roles), grants.c.menu_id.in_(node_menus)))
    bind.execute(nodes.update().where(nodes.c.protocol == "local", nodes.c.host == "static/upload")
        .values(host="data/archive", description="私有档案存储，不公开静态访问"))


def downgrade():
    # 权限调整不恢复匿名存储浏览；回滚业务版本前应导出档案元数据。
    pass
