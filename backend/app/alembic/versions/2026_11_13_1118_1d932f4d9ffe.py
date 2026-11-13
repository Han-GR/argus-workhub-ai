"""内部任务的优先级、截止日期和附件。

Revision ID: 1d932f4d9ffe
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "1d932f4d9ffe"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sys_ticket")}
    additions = [
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("attachment_url", sa.Text(), nullable=True),
    ]
    for column in additions:
        if column.name not in columns:
            op.add_column("sys_ticket", column)
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("sys_ticket")}
    if "ix_sys_ticket_due_date" not in indexes:
        op.create_index("ix_sys_ticket_due_date", "sys_ticket", ["due_date"])


def downgrade():
    op.drop_index("ix_sys_ticket_due_date", table_name="sys_ticket")
    for name in ["attachment_url", "due_date", "priority"]:
        op.drop_column("sys_ticket", name)
