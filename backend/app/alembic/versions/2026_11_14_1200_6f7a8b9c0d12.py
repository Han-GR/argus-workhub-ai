"""任务协同目录：我的任务、会议纪要。"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "6f7a8b9c0d12"
down_revision = "5e6f7a8b9c01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    menu = sa.Table("sys_menu", metadata, autoload_with=bind)
    grants = sa.Table("sys_role_menus", metadata, autoload_with=bind)
    task = bind.execute(sa.select(menu).where(menu.c.route_name == "ModuleTicket")).mappings().one_or_none()
    if task is None:
        return
    now = datetime.now(UTC)
    defaults = {"status": task["status"], "hidden": task["hidden"], "scope": task["scope"],
                "keep_alive": True, "always_show": False, "affix": False, "is_iframe": False,
                "is_hide_tab": False, "show_badge": False, "is_deleted": task["is_deleted"],
                "created_time": now, "updated_time": now}
    parent_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == "TaskCollaboration")).scalar_one_or_none()
    if parent_id is None:
        parent_id = bind.execute(menu.insert().values(**(defaults | {"uuid": str(uuid4()),
            "name": "任务协同", "title": "任务协同", "type": 1, "order": 20,
            "route_name": "TaskCollaboration", "route_path": "/collaboration", "icon": "ri:feedback-line",
            "redirect": "/system/ticket", "always_show": True}))).inserted_primary_key[0]
    meeting_id = bind.execute(sa.select(menu.c.id).where(menu.c.route_name == "MeetingMinutes")).scalar_one_or_none()
    if meeting_id is None:
        meeting_id = bind.execute(menu.insert().values(**defaults, uuid=str(uuid4()), name="会议纪要",
            title="会议纪要", type=2, order=2, parent_id=parent_id, route_name="MeetingMinutes",
            route_path="/collaboration/meetings", component_path="module_system/ticket/meeting",
            icon="ri:file-list-3-line", permission="module_system:ticket:create")).inserted_primary_key[0]
    bind.execute(menu.update().where(menu.c.id == task["id"]).values(
        parent_id=parent_id, name="我的任务", title="我的任务", order=1, updated_time=now))
    readers = set(bind.execute(sa.select(grants.c.role_id).where(grants.c.menu_id == task["id"])).scalars())
    creators = set(bind.execute(sa.select(grants.c.role_id).join(menu, menu.c.id == grants.c.menu_id)
        .where(menu.c.permission == "module_system:ticket:create", menu.c.status == 0, menu.c.is_deleted.is_(False))).scalars())
    for menu_id, roles in [(parent_id, readers), (meeting_id, readers & creators)]:
        for role_id in roles:
            if not bind.execute(sa.select(grants.c.role_id).where(grants.c.role_id == role_id, grants.c.menu_id == menu_id)).first():
                bind.execute(grants.insert().values(role_id=role_id, menu_id=menu_id))


def downgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    menu = sa.Table("sys_menu", metadata, autoload_with=bind)
    grants = sa.Table("sys_role_menus", metadata, autoload_with=bind)
    ids = list(bind.execute(sa.select(menu.c.id).where(menu.c.route_name.in_(["TaskCollaboration", "MeetingMinutes"]))).scalars())
    bind.execute(menu.update().where(menu.c.route_name == "ModuleTicket").values(
        parent_id=None, name="任务协同", title="任务协同", order=20))
    bind.execute(grants.delete().where(grants.c.menu_id.in_(ids)))
    bind.execute(menu.delete().where(menu.c.id.in_(ids)))
