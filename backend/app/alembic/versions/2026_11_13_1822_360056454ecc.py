"""企业知识库、部门共享、独立菜单。新功能不迁移个人文档。"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "360056454ecc"
down_revision = "8b9c0d1e2f34"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("ai_knowledge_document")}
    if "owner_id" in columns and bind.execute(sa.text("SELECT COUNT(*) FROM ai_knowledge_document")).scalar():
        raise RuntimeError("企业知识库为全新功能，不迁移个人文档；请先确认并清空旧知识库文档后再升级")
    # MySQL DDL 不随事务回滚，允许恢复开发热重载中断留下的部分结构。
    if not inspector.has_table("ai_knowledge_base"):
        op.create_table("ai_knowledge_base",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("dept_id", sa.Integer(), sa.ForeignKey("sys_dept.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("created_time", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ai_knowledge_base_dept_id", "ai_knowledge_base", ["dept_id"])
    indexes = {i["name"] for i in inspector.get_indexes("ai_knowledge_document")}
    foreign_keys = inspector.get_foreign_keys("ai_knowledge_document")
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("ai_knowledge_document", naming_convention=naming) as batch:
        if "base_id" not in columns:
            batch.add_column(sa.Column("base_id", sa.String(36), nullable=False))
        if "uploaded_by" not in columns:
            batch.add_column(sa.Column("uploaded_by", sa.Integer(), nullable=True))
        for fk in foreign_keys:
            if fk["constrained_columns"] == ["owner_id"]:
                batch.drop_constraint(fk["name"] or "fk_ai_knowledge_document_owner_id_sys_user", type_="foreignkey")
        if "ix_ai_knowledge_document_owner_id" in indexes:
            batch.drop_index("ix_ai_knowledge_document_owner_id")
        if "ix_ai_knowledge_document_base_id" not in indexes:
            batch.create_index("ix_ai_knowledge_document_base_id", ["base_id"])
        for column, target, ondelete in [("base_id", "ai_knowledge_base", "RESTRICT"), ("uploaded_by", "sys_user", "SET NULL")]:
            if not any(fk["constrained_columns"] == [column] for fk in foreign_keys):
                batch.create_foreign_key(f"fk_ai_knowledge_document_{column}_{target}", target, [column], ["id"], ondelete=ondelete)
        if "owner_id" in columns:
            batch.drop_column("owner_id")
    menu = sa.Table("sys_menu", sa.MetaData(), autoload_with=bind)
    now = datetime.now(UTC)
    defaults = {"status": 0, "hidden": False, "keep_alive": True, "always_show": False, "affix": False,
                "is_iframe": False, "is_hide_tab": False, "show_badge": False, "scope": "web",
                "uuid": str(uuid4()), "is_deleted": False, "created_time": now, "updated_time": now}
    result = bind.execute(menu.insert().values(**defaults, name="知识库", title="知识库", type=2, order=25,
        permission="module_ai:knowledge:query", icon="ri:book-open-line", route_name="Knowledge",
        route_path="/knowledge", component_path="module_ai/knowledge/index"))
    parent_id = result.inserted_primary_key[0]
    for order, (name, permission) in enumerate([("全局维护", "manage"), ("本部门维护", "department")], 1):
        bind.execute(menu.insert().values(**(defaults | {"uuid": str(uuid4())}), name=name, title=name,
            type=3, order=order, parent_id=parent_id, permission="module_ai:knowledge:" + permission))


def downgrade():
    # 旧的个人文档结构无法承载共享资料，禁止隐式降级造成权限语义变化。
    raise RuntimeError("企业知识库不支持降级到个人知识库；如需回退请恢复数据库备份")
