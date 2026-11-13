from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.enums import TicketTypeEnum
from app.core.base_schema import (
    BaseQueryParam,
    BaseSchema,
    CommonSchema,
    UserByQueryParam,
    UserBySchema,
)


class TicketCreateSchema(BaseModel):
    """创建任务"""

    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    ticket_content: str = Field(default="", description="任务内容（富文本）")
    summary: str | None = Field(default=None, description="任务内容（纯文本摘要）")
    ticket_type: TicketTypeEnum = Field(default=TicketTypeEnum.SUGGESTION, description="任务类型(suggestion/bug/optimize/other)")
    images: str | None = Field(default=None, description="图片URL列表(JSON数组)")
    description: str | None = Field(default=None, max_length=255, description="任务描述")

    assigned_id: int | None = Field(default=None, gt=0, description="负责人ID")
    priority: int = Field(default=1, ge=0, le=3, description="优先级")
    due_date: date | None = Field(default=None, description="截止日期")
    attachment_url: str | None = Field(default=None, max_length=2048, description="任务附件")

    @field_validator("attachment_url")
    @classmethod
    def _validate_attachment(cls, value: str | None) -> str | None:
        if not value:
            return None
        url = urlsplit(value)
        if "\\" in value or any(ord(c) < 32 for c in value) or (url.scheme and not url.netloc) or url.scheme not in ("http", "https", "") or (not url.scheme and (not value.startswith("/") or value.startswith("//"))):
            raise ValueError("附件地址无效")
        return value

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("任务标题不能为空")
        return v


class TicketUpdateSchema(BaseModel):
    """更新任务"""

    title: str | None = Field(default=None, max_length=200, description="任务标题")
    ticket_content: str | None = Field(default=None, description="任务内容（富文本）")
    summary: str | None = Field(default=None, description="任务内容（纯文本摘要）")
    ticket_type: TicketTypeEnum | None = Field(default=None, description="任务类型")
    status: int | None = Field(default=None, ge=0, le=3, description="状态(0:待开始 1:进行中 2:已完成 3:已取消)")
    reply: str | None = Field(default=None, description="回复内容")
    assigned_id: int | None = Field(default=None, gt=0, description="负责人ID")
    description: str | None = Field(default=None, max_length=255, description="任务描述")


    @field_validator("title", "ticket_type", "status", "priority")
    @classmethod
    def _reject_empty_required_fields(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("任务字段不能为空")
        return value.strip() if isinstance(value, str) else value

    priority: int | None = Field(default=None, ge=0, le=3, description="优先级")
    due_date: date | None = Field(default=None, description="截止日期")
    attachment_url: str | None = Field(default=None, max_length=2048, description="任务附件")

    @field_validator("attachment_url")
    @classmethod
    def _validate_attachment(cls, value: str | None) -> str | None:
        if not value:
            return None
        url = urlsplit(value)
        if "\\" in value or any(ord(c) < 32 for c in value) or (url.scheme and not url.netloc) or url.scheme not in ("http", "https", "") or (not url.scheme and (not value.startswith("/") or value.startswith("//"))):
            raise ValueError("附件地址无效")
        return value


class TicketOutSchema(BaseSchema, UserBySchema):
    created_id: int | None = None
    """任务响应"""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="任务标题")
    ticket_content: str | None = Field(default=None, description="任务内容")
    summary: str | None = Field(default=None, description="摘要")
    ticket_type: TicketTypeEnum = Field(..., description="任务类型")
    status: int = Field(..., description="状态(0:待开始 1:进行中 2:已完成 3:已取消)")
    images: str | None = Field(default=None, description="图片")
    reply: str | None = Field(default=None, description="回复内容")
    assigned_id: int | None = Field(default=None, description="指派人ID")
    assigned_by: CommonSchema | None = Field(default=None, description="指派人")


    priority: int = 1
    due_date: date | None = None
    attachment_url: str | None = None


class TicketBatchSchema(BaseModel):
    """批量更新任务"""

    ids: list[int] = Field(..., min_length=1, description="任务ID列表")
    status: int = Field(..., ge=0, le=3, description="状态(0:待开始 1:进行中 2:已完成 3:已取消)")


class TicketStatsSchema(BaseModel):
    """任务状态聚合统计（已取消不计入）"""

    pending: int = Field(default=0, description="待开始数量")
    processing: int = Field(default=0, description="进行中数量")
    done: int = Field(default=0, description="已完成数量")


class TicketQueryParam(BaseQueryParam, UserByQueryParam):
    """任务查询参数"""

    view: Literal["all", "assigned", "created"] = Field(default="all", exclude=True, description="任务范围")
    priority: int | None = Field(default=None, ge=0, le=3, json_schema_extra={"q": "eq"})
    title: str | None = Field(None, description="任务标题", json_schema_extra={"q": "like"})
    ticket_type: str | None = Field(None, description="任务类型", json_schema_extra={"q": "eq"})
    assigned_id: int | None = Field(None, description="负责人ID", json_schema_extra={"q": "eq"})
    status: int | None = Field(None, ge=0, le=3, description="状态(0:待开始 1:进行中 2:已完成 3:已取消)", json_schema_extra={"q": "eq"})


class TicketCommentCreateSchema(BaseModel):
    """创建评论"""
    content: str = Field(..., min_length=1, max_length=5000, description="评论内容")

    @field_validator("content")
    @classmethod
    def _nonempty_comment(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("评论不能为空")
        return value.strip()


class TicketCommentOutSchema(BaseSchema, UserBySchema):
    """评论响应"""
    model_config = ConfigDict(from_attributes=True)
    ticket_id: int
    content: str
    created_by_name: str | None = None
