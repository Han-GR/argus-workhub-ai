"""按文档共享范围及上传者授权，保留原文和已有向量索引。"""
import sqlalchemy as sa
from alembic import op

revision = "4d5e6f7a8b90"
down_revision = "360056454ecc"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("ai_knowledge_document")}
    # 默认不可见，MySQL DDL 中断时也不能把部门文件意外公开。
    with op.batch_alter_table("ai_knowledge_document") as batch:
        if "visibility" not in columns:
            batch.add_column(sa.Column("visibility", sa.String(20), nullable=False, server_default="department"))
        if "dept_id" not in columns:
            batch.add_column(sa.Column("dept_id", sa.Integer(), nullable=True))
        if "index_namespace" not in columns:
            batch.add_column(sa.Column("index_namespace", sa.String(36), nullable=True))
    if "base_id" in columns:
        missing = bind.execute(sa.text("SELECT COUNT(*) FROM ai_knowledge_document d LEFT JOIN ai_knowledge_base b ON b.id = d.base_id WHERE b.id IS NULL")).scalar()
        if missing:
            raise RuntimeError("文档找不到所属知识库，无法确认原可见范围，已停止迁移")
        bind.execute(sa.text("""UPDATE ai_knowledge_document SET
            visibility = CASE WHEN (SELECT dept_id FROM ai_knowledge_base WHERE id = ai_knowledge_document.base_id) IS NULL THEN 'company' ELSE 'department' END,
            dept_id = (SELECT dept_id FROM ai_knowledge_base WHERE id = ai_knowledge_document.base_id),
            index_namespace = base_id"""))
    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys("ai_knowledge_document")
    indexes = {i["name"] for i in inspector.get_indexes("ai_knowledge_document")}
    checks = {c["name"] for c in inspector.get_check_constraints("ai_knowledge_document")}
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("ai_knowledge_document", naming_convention=naming) as batch:
        for fk in foreign_keys:
            if fk["constrained_columns"] == ["base_id"]:
                batch.drop_constraint(fk["name"] or "fk_ai_knowledge_document_base_id_ai_knowledge_base", type_="foreignkey")
        if "ix_ai_knowledge_document_base_id" in indexes:
            batch.drop_index("ix_ai_knowledge_document_base_id")
        if "base_id" in columns:
            batch.drop_column("base_id")
        batch.alter_column("index_namespace", existing_type=sa.String(36), nullable=False)
        if not any(fk["constrained_columns"] == ["dept_id"] for fk in foreign_keys):
            batch.create_foreign_key("fk_ai_knowledge_document_dept_id_sys_dept", "sys_dept", ["dept_id"], ["id"], ondelete="RESTRICT")
        if "ix_ai_knowledge_document_visibility_dept" not in indexes:
            batch.create_index("ix_ai_knowledge_document_visibility_dept", ["visibility", "dept_id"])
        if "ck_ai_knowledge_document_visibility" not in checks:
            batch.create_check_constraint("ck_ai_knowledge_document_visibility", "(visibility = 'company' AND dept_id IS NULL) OR (visibility = 'department' AND dept_id IS NOT NULL)")
    if inspector.has_table("ai_knowledge_base"):
        op.drop_table("ai_knowledge_base")
    bind.execute(sa.text("DELETE FROM sys_role_menus WHERE menu_id IN (SELECT id FROM sys_menu WHERE permission IN ('module_ai:knowledge:manage', 'module_ai:knowledge:department'))"))
    bind.execute(sa.text("DELETE FROM sys_menu WHERE permission IN ('module_ai:knowledge:manage', 'module_ai:knowledge:department')"))


def downgrade():
    raise RuntimeError("文档级共享不能自动降级为知识库级共享；请恢复备份")
