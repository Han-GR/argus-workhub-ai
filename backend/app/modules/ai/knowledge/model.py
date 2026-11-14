from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase


class KnowledgeDocumentModel(MappedBase):
    __tablename__ = "ai_knowledge_document"
    __table_args__ = (
        CheckConstraint("(visibility = 'company' AND dept_id IS NULL) OR (visibility = 'department' AND dept_id IS NOT NULL)", name="visibility"),
        Index("ix_ai_knowledge_document_visibility_dept", "visibility", "dept_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="department")
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dept.id", ondelete="RESTRICT"), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True)
    index_namespace: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
