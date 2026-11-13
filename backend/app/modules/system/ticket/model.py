from uuid import uuid4
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base_model import MappedBase, ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.modules.system.user.model import UserModel


class TicketModel(ModelMixin, UserMixin):
    """任务模型 — 内部团队协作任务
    status: 0=待开始 1=进行中 2=已完成 3=已取消
    """

    __tablename__: str = "sys_ticket"
    __table_args__ = (Index("uq_task_meeting_item", "source_meeting_id", "source_item_index", unique=True), {"comment": "任务表"})

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="标题")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:待开始 1:进行中 2:已完成 3:已取消)")
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="备注")
    ticket_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务内容（富文本）")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务内容（纯文本摘要）")
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False, default="suggestion", comment="任务类型(suggestion:建议 bug:缺陷 optimize:优化 other:其他)")
    images: Mapped[str | None] = mapped_column(Text, nullable=True, comment="图片URL列表(JSON数组)")
    reply: Mapped[str | None] = mapped_column(Text, nullable=True, comment="回复内容")
    assigned_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="负责人ID")

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1", comment="优先级(0低/1普通/2高/3紧急)")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True, comment="截止日期")
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务附件地址")

    source_meeting_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sys_meeting_task_draft.id", name="fk_ticket_meeting_draft", ondelete="SET NULL"), nullable=True)
    source_item_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    assigned_by: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys=[assigned_id], uselist=False)

    @validates("title")
    def validate_title(self, key: str, title: str) -> str:
        if not title or not title.strip():
            raise ValueError("任务标题不能为空")
        return title.strip()

    @validates("summary", "ticket_content")
    def validate_content(self, key: str, content: str | None) -> str | None:
        if content and content.strip():
            return content.strip()
        return content


class TicketCommentModel(ModelMixin, UserMixin):
    """任务评论模型"""
    __tablename__: str = "sys_ticket_comment"
    __table_args__: dict[str, str] = {"comment": "任务评论表"}

    ticket_id: Mapped[int] = mapped_column(ForeignKey("sys_ticket.id", ondelete="CASCADE"), nullable=False, index=True, comment="任务ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容（富文本）")


class TaskNotificationModel(MappedBase):
    """站内任务消息，读取范围由收件人与当前任务权限共同约束。"""
    __tablename__ = "sys_task_notification"
    __table_args__ = (Index("ix_task_notification_recipient_created", "recipient_id", "created_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("sys_ticket.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class MeetingTaskDraftModel(MappedBase):
    """仅所有者可访问的会议原文、草稿和确认回执。"""
    __tablename__ = "sys_meeting_task_draft"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    drafts: Mapped[list] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False)
    confirmed_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_tasks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_task_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
