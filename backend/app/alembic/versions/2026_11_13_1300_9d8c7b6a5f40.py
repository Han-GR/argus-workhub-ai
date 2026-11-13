"""恢复参数管理和存储源管理入口，沿用既有角色权限。"""
from alembic import op
import sqlalchemy as sa

revision = "9d8c7b6a5f40"
down_revision = "7e440d516fd5"
branch_labels = None
depends_on = None


def upgrade():
    table = sa.table("sys_menu", sa.column("route_name", sa.String), sa.column("hidden", sa.Boolean), sa.column("name", sa.String), sa.column("title", sa.String))
    op.execute(table.update().where(table.c.route_name.in_(["Params", "WorkflowNode"])).values(hidden=False))
    op.execute(table.update().where(table.c.route_name == "WorkflowNode").values(name="存储源管理", title="存储源管理"))


def downgrade():
    table = sa.table("sys_menu", sa.column("route_name", sa.String), sa.column("hidden", sa.Boolean), sa.column("name", sa.String), sa.column("title", sa.String))
    op.execute(table.update().where(table.c.route_name.in_(["Params", "WorkflowNode"])).values(hidden=True))
    op.execute(table.update().where(table.c.route_name == "WorkflowNode").values(name="节点管理", title="节点管理"))
