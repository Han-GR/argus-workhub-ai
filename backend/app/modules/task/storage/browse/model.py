from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase


class ArchiveEntryModel(MappedBase):
    """逻辑档案目录；对象键不对外暴露，子项共享范围由根条目决定。"""

    __tablename__ = "task_archive_entry"
    __table_args__ = (
        UniqueConstraint("source_id", "bucket", "path", name="uq_archive_path"),
        CheckConstraint("visibility IN ('private', 'department', 'company')", name="visibility"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("task_storage_node.id", ondelete="RESTRICT"), nullable=False)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("task_archive_entry.id", ondelete="RESTRICT"))
    is_dir: Mapped[bool] = mapped_column(Boolean, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(100))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dept.id", ondelete="SET NULL"))
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    size: Mapped[int | None] = mapped_column(Integer)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
