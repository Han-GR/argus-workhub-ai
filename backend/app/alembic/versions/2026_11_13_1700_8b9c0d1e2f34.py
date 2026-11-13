"""个人知识库文档。"""
from alembic import op
import sqlalchemy as sa

revision = "8b9c0d1e2f34"
down_revision = "6a7b8c9d0e12"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("ai_knowledge_document"):
        op.create_table("ai_knowledge_document",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("dimensions", sa.Integer(), nullable=False),
            sa.Column("chunk_count", sa.Integer(), nullable=False),
            sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ai_knowledge_document_owner_id", "ai_knowledge_document", ["owner_id"])


def downgrade():
    op.drop_index("ix_ai_knowledge_document_owner_id", table_name="ai_knowledge_document")
    op.drop_table("ai_knowledge_document")
