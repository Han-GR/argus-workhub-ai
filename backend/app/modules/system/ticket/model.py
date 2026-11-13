from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.modules.system.user.model import UserModel


class TicketModel(ModelMixin, UserMixin):
    """任务模型 — 内部团队协作任务
    status: 0=待开始 1=进行中 2=已完成 3=已取消
    """

    __tablename__: str = "sys_ticket"
    __table_args__: dict[str, str] = {"comment": "任务表"}

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
