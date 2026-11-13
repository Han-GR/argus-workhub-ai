"""任务站内消息。"""
from alembic import op
import sqlalchemy as sa

revision = "4f5e6d7c8b90"
down_revision = "9d8c7b6a5f40"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("sys_task_notification"):
        return
    op.create_table(
        "sys_task_notification",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("sys_ticket.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("dedup_key", sa.String(160), nullable=False, unique=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_notification_recipient_created", "sys_task_notification", ["recipient_id", "created_time"])


def downgrade():
    op.drop_index("ix_task_notification_recipient_created", table_name="sys_task_notification")
    op.drop_table("sys_task_notification")
