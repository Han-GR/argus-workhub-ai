from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase


class KnowledgeBaseModel(MappedBase):
    __tablename__ = "ai_knowledge_base"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # RESTRICT 防止部门删除时把部门资料变成全公司可见。
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dept.id", ondelete="RESTRICT"), nullable=True, index=True)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class KnowledgeDocumentModel(MappedBase):
    __tablename__ = "ai_knowledge_document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    base_id: Mapped[str] = mapped_column(ForeignKey("ai_knowledge_base.id", ondelete="RESTRICT"), nullable=False, index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
