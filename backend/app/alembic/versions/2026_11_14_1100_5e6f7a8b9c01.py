"""知识库拆分为文档管理和知识问答，保留既有角色访问权限。"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "5e6f7a8b9c01"
down_revision = "4d5e6f7a8b90"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    menu = sa.Table("sys_menu", metadata, autoload_with=bind)
    grants = sa.Table("sys_role_menus", metadata, autoload_with=bind)
    now = datetime.now(UTC)
    defaults = {"status": 0, "hidden": False, "keep_alive": True, "always_show": False,
                "affix": False, "is_iframe": False, "is_hide_tab": False, "show_badge": False,
                "scope": "web", "is_deleted": False, "created_time": now, "updated_time": now}
    parent = bind.execute(sa.select(menu).where(menu.c.route_name == "Knowledge")).mappings().one_or_none()
    if parent is None:
        parent_id = bind.execute(menu.insert().values(**defaults, uuid=str(uuid4()), name="知识库", title="知识库",
            type=1, order=25, route_name="Knowledge", route_path="/knowledge", icon="ri:book-open-line")).inserted_primary_key[0]
        parent = bind.execute(sa.select(menu).where(menu.c.id == parent_id)).mappings().one()
    parent_id = parent["id"]
    roles = bind.execute(sa.select(grants.c.role_id).where(grants.c.menu_id == parent_id)).scalars().all()
    for order, (name, route_name, route_path, component, icon) in enumerate([
        ("文档管理", "KnowledgeDocuments", "documents", "module_ai/knowledge/index", "ri:file-upload-line"),
        ("知识问答", "KnowledgeQuestion", "question", "module_ai/knowledge/question", "ri:question-answer-line"),
    ], 1):
        child_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == route_name)).scalar_one_or_none()
        if child_id is None:
            values = defaults | {"uuid": str(uuid4()), "name": name, "title": name, "type": 2, "order": order,
                "route_name": route_name, "route_path": route_path, "component_path": component, "icon": icon,
                "permission": "module_ai:knowledge:query", "parent_id": parent_id,
                "status": parent["status"], "is_deleted": parent["is_deleted"], "hidden": parent["hidden"], "scope": parent["scope"]}
            child_id = bind.execute(menu.insert().values(**values)).inserted_primary_key[0]
        for role_id in roles:
            if not bind.execute(sa.select(grants.c.role_id).where(grants.c.role_id == role_id, grants.c.menu_id == child_id)).first():
                bind.execute(grants.insert().values(role_id=role_id, menu_id=child_id))
    bind.execute(menu.update().where(menu.c.id == parent_id).values(type=1, component_path=None,
        permission=None, redirect="/knowledge/documents", always_show=True, updated_time=now))


def downgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    menu = sa.Table("sys_menu", metadata, autoload_with=bind)
    grants = sa.Table("sys_role_menus", metadata, autoload_with=bind)
    parent_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == "Knowledge")).scalar_one_or_none()
    if parent_id is None:
        return
    children = list(bind.execute(sa.select(menu.c.id).where(menu.c.parent_id == parent_id,
        menu.c.route_name.in_(["KnowledgeDocuments", "KnowledgeQuestion"]))).scalars())
    roles = bind.execute(sa.select(grants.c.role_id).where(grants.c.menu_id.in_(children)).distinct()).scalars().all()
    for role_id in roles:
        if not bind.execute(sa.select(grants.c.role_id).where(grants.c.role_id == role_id, grants.c.menu_id == parent_id)).first():
            bind.execute(grants.insert().values(role_id=role_id, menu_id=parent_id))
    bind.execute(grants.delete().where(grants.c.menu_id.in_(children)))
    bind.execute(menu.delete().where(menu.c.id.in_(children)))
    bind.execute(menu.update().where(menu.c.id == parent_id).values(type=2, component_path="module_ai/knowledge/index",
        permission="module_ai:knowledge:query", redirect=None, always_show=False))
