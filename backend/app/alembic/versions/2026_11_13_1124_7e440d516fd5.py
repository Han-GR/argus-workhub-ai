"""更新内部任务字段说明，不修改已有数据。"""
from alembic import op
import sqlalchemy as sa

revision = "7e440d516fd5"
down_revision = "1d932f4d9ffe"
branch_labels = None
depends_on = None


def _comments(reverse=False):
    if op.get_bind().dialect.name == "sqlite":
        return  # SQLite 不支持表和字段注释。
    fields = [
        ("sys_ticket", "status", sa.Integer(), False, "状态(0:待处理 1:处理中 2:已完成 3:已关闭)", "状态(0:待开始 1:进行中 2:已完成 3:已取消)"),
        ("sys_ticket", "ticket_content", sa.Text(), True, "工单内容（富文本）", "任务内容（富文本）"),
        ("sys_ticket", "summary", sa.Text(), True, "工单内容（纯文本摘要）", "任务内容（纯文本摘要）"),
        ("sys_ticket", "ticket_type", sa.String(20), False, "工单类型(suggestion:建议 bug:缺陷 optimize:优化 other:其他)", "任务类型(suggestion:建议 bug:缺陷 optimize:优化 other:其他)"),
        ("sys_ticket", "assigned_id", sa.Integer(), True, "处理人ID", "负责人ID"),
        ("sys_ticket_comment", "ticket_id", sa.Integer(), False, "工单ID", "任务ID"),
    ]
    for table, field, kind, nullable, old, new in fields:
        op.alter_column(table, field, existing_type=kind, existing_nullable=nullable, comment=old if reverse else new, existing_comment=new if reverse else old)
    for table, old, new in [("sys_ticket", "工单表", "任务表"), ("sys_ticket_comment", "工单评论表", "任务评论表")]:
        op.create_table_comment(table, old if reverse else new, existing_comment=new if reverse else old)


def upgrade():
    _comments()


def downgrade():
    _comments(reverse=True)
