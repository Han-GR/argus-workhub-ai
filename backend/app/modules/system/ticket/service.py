from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.system.user.model import UserModel
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from .crud import TicketCommentCRUD, TicketCRUD
from .notifications import notify_task
from .schema import (
    TicketBatchSchema,
    TicketCommentCreateSchema,
    TicketCommentOutSchema,
    TicketCreateSchema,
    TicketOutSchema,
    TicketQueryParam,
    TicketStatsSchema,
    TicketUpdateSchema,
)

_TICKET_STATUS_TRANSITIONS = {0: {1, 3}, 1: {0, 2, 3}, 2: {1, 3}, 3: {0}}
_TICKET_STATUS_LABELS = {0: "待开始", 1: "进行中", 2: "已完成", 3: "已取消"}


_TICKET_PRELOAD = ["assigned_by"]


class TicketService:
    """任务管理服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    def _can_manage(self, task) -> bool:
        user = self.auth.user
        return bool(user and (user.is_superuser or user.id == task.created_id))

    def _can_edit(self, task) -> bool:
        user = self.auth.user
        return self._can_manage(task) or bool(user and user.id == task.assigned_id)

    def _validate_status_transition(self, ticket, new_status: int) -> None:
        if not self._can_edit(ticket):
            raise CustomException(msg="仅创建人、负责人或管理员可以更新任务")
        old_status = ticket.status if ticket.status is not None else 0
        if new_status == old_status:
            return
        if new_status not in _TICKET_STATUS_TRANSITIONS.get(old_status, set()):
            raise CustomException(msg=f"不允许从{_TICKET_STATUS_LABELS.get(old_status)}转换为{_TICKET_STATUS_LABELS.get(new_status)}")
        if (new_status == 3 or old_status == 3) and not self._can_manage(ticket):
            raise CustomException(msg="仅创建人或管理员可以取消或重新打开任务")

    def _search(self, search: TicketQueryParam | None) -> dict:
        conditions = search_to_dict(search) or {}
        view = search.view if search else "all"
        conditions.pop("view", None)
        if view in ("assigned", "created"):
            conditions["assigned_id" if view == "assigned" else "created_id"] = ("eq", self.auth.user.id)
        return conditions

    async def assignees(self) -> list[dict]:
        # 内部任务可选择在职同事，仅返回分配任务需要的公开目录信息。
        rows = (await self.db.execute(select(UserModel.id, UserModel.name, UserModel.username).where(UserModel.status == 0, UserModel.is_deleted.is_(False)).order_by(UserModel.id))).all()
        return [dict(id=row.id, name=row.name, username=row.username) for row in rows]

    async def _validate_assignee(self, uid: int | None) -> None:
        if uid is None:
            return
        exists = await self.db.scalar(select(UserModel.id).where(UserModel.id == uid, UserModel.status == 0, UserModel.is_deleted.is_(False)))
        if exists is None:
            raise CustomException(msg="负责人不存在或已停用")

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: TicketQueryParam | None = None,
        order_by: list | None = None,
    ) -> PageResultSchema[TicketOutSchema]:
        return await TicketCRUD(self.auth, self.db).page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"created_time": "desc"}],
            search=self._search(search),
            out_schema=TicketOutSchema,
            preload=_TICKET_PRELOAD,
        )

    async def detail(self, id: int) -> TicketOutSchema:
        obj = await TicketCRUD(self.auth, self.db).get_or_404(id=id, preload=_TICKET_PRELOAD)
        return TicketOutSchema.model_validate(obj)

    async def create(self, data: TicketCreateSchema, *, source_meeting_id: str | None = None, source_item_index: int | None = None) -> TicketOutSchema:
        await self._validate_assignee(getattr(data, "assigned_id", None))
        values = data
        if source_meeting_id is not None:
            values = data.model_dump() | {"source_meeting_id": source_meeting_id, "source_item_index": source_item_index}
        obj = await TicketCRUD(self.auth, self.db).create(data=values)
        if not obj:
            raise CustomException(msg="创建任务失败")
        if getattr(obj, "assigned_id", None):
            await notify_task(self.db, obj, self.auth.user.id, "assigned", "你被指定为任务负责人", recipients={obj.assigned_id})
        return await self.detail(id=obj.id)

    async def update(self, id: int, data: TicketUpdateSchema) -> TicketOutSchema:
        obj = await TicketCRUD(self.auth, self.db).get_or_404(id=id, msg="任务不存在")

        if not self._can_edit(obj):
            raise CustomException(msg="仅创建人、负责人或管理员可以编辑任务")
        if data.status is not None:
            self._validate_status_transition(obj, data.status)
        fields = getattr(data, "model_fields_set", set())
        if "assigned_id" in fields and data.assigned_id != obj.assigned_id:
            if not self._can_manage(obj):
                raise CustomException(msg="仅创建人或管理员可以更换负责人")
            await self._validate_assignee(data.assigned_id)

        old_assignee, old_status = obj.assigned_id, obj.status
        updated = await TicketCRUD(self.auth, self.db).update(id=id, data=data)
        if not updated:
            raise CustomException(msg="任务不存在")

        if updated.assigned_id and updated.assigned_id != old_assignee:
            await notify_task(self.db, updated, self.auth.user.id, "assigned", "你被指定为任务负责人", recipients={updated.assigned_id})
        if updated.status != old_status:
            await notify_task(self.db, updated, self.auth.user.id, "status", f"任务状态更新为：{_TICKET_STATUS_LABELS[updated.status]}")
        return await self.detail(id=updated.id)

    async def delete(self, ids: list[int]) -> None:
        if not ids:
            raise CustomException(msg="删除对象不能为空")
        for tid in ids:
            task = await TicketCRUD(self.auth, self.db).get_or_404(id=tid)
            if not self._can_manage(task):
                raise CustomException(msg="仅创建人或管理员可以删除任务")
        await TicketCRUD(self.auth, self.db).delete(ids=ids)

    async def batch(self, data: TicketBatchSchema) -> None:
        if not data.ids:
            raise CustomException(msg="请选择要操作的任务")

        tickets = await TicketCRUD(self.auth, self.db).get_list(search={"id": ("in", data.ids)})
        ticket_map = {t.id: t for t in tickets}
        for tid in data.ids:
            obj = ticket_map.get(tid)
            if not obj:
                raise CustomException(msg=f"任务[{tid}]不存在")
            self._validate_status_transition(obj, data.status)
        changed = [task for task in tickets if task.status != data.status]
        await TicketCRUD(self.auth, self.db).set(ids=data.ids, status=data.status)
        for task in changed:
            await notify_task(self.db, task, self.auth.user.id, "status", f"任务状态更新为：{_TICKET_STATUS_LABELS[data.status]}")

    async def get_list(
        self,
        search: TicketQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> list[TicketOutSchema]:
        obj_list = await TicketCRUD(self.auth, self.db).get_list(
            search=self._search(search),
            order_by=order_by or [{"created_time": "desc"}],
            preload=_TICKET_PRELOAD,
        )
        return [TicketOutSchema.model_validate(obj) for obj in obj_list]

    async def stats(self) -> TicketStatsSchema:
        """按状态聚合任务数量（待开始/进行中/已完成，已取消不计入）。

        走 CRUDBase.count 以统一继承软删过滤与数据权限；同一 AsyncSession
        不能并发执行，三次 COUNT 顺序发起。
        """
        crud = TicketCRUD(self.auth, self.db)
        return TicketStatsSchema(
            pending=await crud.count(status=("eq", 0)),
            processing=await crud.count(status=("eq", 1)),
            done=await crud.count(status=("eq", 2)),
        )

    @staticmethod
    async def export_list(ticket_list: list[dict[str, Any]]) -> bytes:
        """导出任务列表"""
        mapping_dict = {
            "id": "任务编号",
            "title": "任务标题",
            "ticket_type": "任务类型",
            "summary": "任务摘要",
            "status": "任务状态",
            "priority": "优先级",
            "due_date": "截止日期",
            "assigned_id": "负责人ID",
            "description": "备注",
            "created_time": "创建时间",
            "updated_time": "更新时间",
        }
        return await ExcelUtil.aexport_list2excel(list_data=ticket_list, mapping_dict=mapping_dict)


class TicketCommentService:
    """任务评论服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(self, ticket_id: int, page_no: int, page_size: int) -> PageResultSchema[TicketCommentOutSchema]:
        await TicketCRUD(self.auth, self.db).get_or_404(id=ticket_id, msg="任务不存在")
        return await TicketCommentCRUD(self.auth, self.db).page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=[{"created_time": "desc"}],
            search={"ticket_id": ("eq", ticket_id)},
            out_schema=TicketCommentOutSchema,
        )

    async def create(self, ticket_id: int, data: TicketCommentCreateSchema) -> TicketCommentOutSchema:
        # 验证任务存在
        task = await TicketCRUD(self.auth, self.db).get_or_404(id=ticket_id, msg="任务不存在")
        create_data = data.model_dump() | {"ticket_id": ticket_id}
        obj = await TicketCommentCRUD(self.auth, self.db).create(data=create_data)  # type: ignore[arg-type]
        if not obj:
            raise CustomException(msg="评论失败")
        await notify_task(self.db, task, self.auth.user.id, "comment", "任务有新评论，查看同事的进展")
        return TicketCommentOutSchema.model_validate(obj)

    async def delete(self, comment_id: int) -> None:
        await TicketCommentCRUD(self.auth, self.db).get_or_404(id=comment_id, msg="评论不存在")
        await TicketCommentCRUD(self.auth, self.db).delete(ids=[comment_id])
