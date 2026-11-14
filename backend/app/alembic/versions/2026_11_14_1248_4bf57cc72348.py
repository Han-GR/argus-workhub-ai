"""档案逻辑目录、上传者与共享范围元数据。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bf57cc72348'
down_revision: Union[str, None] = '6f7a8b9c0d12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('task_archive_entry',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('bucket', sa.String(length=100), nullable=False),
    sa.Column('path', sa.String(length=500), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('is_dir', sa.Boolean(), nullable=False),
    sa.Column('object_key', sa.String(length=100), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('dept_id', sa.Integer(), nullable=True),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("visibility IN ('private', 'department', 'company')", name=op.f('ck_task_archive_entry_visibility')),
    sa.ForeignKeyConstraint(['dept_id'], ['sys_dept.id'], name=op.f('fk_task_archive_entry_dept_id_sys_dept'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['owner_id'], ['sys_user.id'], name=op.f('fk_task_archive_entry_owner_id_sys_user'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['parent_id'], ['task_archive_entry.id'], name=op.f('fk_task_archive_entry_parent_id_task_archive_entry'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_id'], ['task_storage_node.id'], name=op.f('fk_task_archive_entry_source_id_task_storage_node'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_task_archive_entry')),
    sa.UniqueConstraint('source_id', 'bucket', 'path', name='uq_archive_path')
    )


def downgrade() -> None:
    op.drop_table('task_archive_entry')
