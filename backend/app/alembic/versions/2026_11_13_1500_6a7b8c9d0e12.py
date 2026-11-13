"""会议任务草稿与确认来源。"""
from alembic import op
import sqlalchemy as sa

revision = "6a7b8c9d0e12"
down_revision = "4f5e6d7c8b90"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("sys_meeting_task_draft"):
        op.create_table("sys_meeting_task_draft",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("reference_date", sa.Date(), nullable=False),
            sa.Column("drafts", sa.JSON(), nullable=False),
            sa.Column("warnings", sa.JSON(), nullable=False),
            sa.Column("confirmed_hash", sa.String(64), nullable=True),
            sa.Column("confirmed_tasks", sa.JSON(), nullable=True),
            sa.Column("created_task_ids", sa.JSON(), nullable=True),
            sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        )
    columns = {c["name"] for c in sa.inspect(bind).get_columns("sys_ticket")}
    with op.batch_alter_table("sys_ticket") as batch:
        if "source_meeting_id" not in columns:
            batch.add_column(sa.Column("source_meeting_id", sa.String(36), nullable=True))
            batch.create_foreign_key("fk_ticket_meeting_draft", "sys_meeting_task_draft", ["source_meeting_id"], ["id"], ondelete="SET NULL")
        if "source_item_index" not in columns:
            batch.add_column(sa.Column("source_item_index", sa.Integer(), nullable=True))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("sys_ticket")}
    if "uq_task_meeting_item" not in indexes:
        op.create_index("uq_task_meeting_item", "sys_ticket", ["source_meeting_id", "source_item_index"], unique=True)


def downgrade():
    with op.batch_alter_table("sys_ticket") as batch:
        batch.drop_index("uq_task_meeting_item")
        batch.drop_constraint("fk_ticket_meeting_draft", type_="foreignkey")
        batch.drop_column("source_item_index")
        batch.drop_column("source_meeting_id")
    op.drop_table("sys_meeting_task_draft")
