from datetime import datetime, timedelta
from typing import Annotated
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, Security
from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.config.setting import settings
from app.core.base_schema import AuthSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.modules.system.user.model import UserModel
from .crud import TicketCRUD
from .model import TaskNotificationModel as Notice, TicketModel as Task


def _today():
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()


async def notify_task(db, task, actor_id, kind, message, *, recipients=None):
    recipients = set(recipients if recipients is not None else [getattr(task, "created_id", None), getattr(task, "assigned_id", None)]) - {None, actor_id}
    if not recipients:
        return
    enabled = (await db.execute(select(UserModel.id).where(UserModel.id.in_(recipients), UserModel.status == 0, UserModel.is_deleted.is_(False)))).scalars().all()
    for uid in enabled:
        db.add(Notice(recipient_id=uid, ticket_id=task.id, kind=kind, message=message, dedup_key=str(uuid4())))
    await db.flush()


class TaskNotificationService:
    def __init__(self, auth: AuthSchema, db: AsyncSession):
        self.auth, self.db = auth, db

    async def _conditions(self):
        today = _today()
        task_conditions = await TicketCRUD(self.auth, self.db)._build_conditions()
        return [
            Notice.recipient_id == self.auth.user.id,
            Notice.ticket_id.in_(select(Task.id).where(*task_conditions).correlate(None)),
            or_(
                Notice.kind.not_in(["due_soon", "overdue"]),
                and_(Task.status.in_([0, 1]), Notice.due_date == Task.due_date,
                     or_(and_(Notice.kind == "due_soon", Task.due_date >= today),
                         and_(Notice.kind == "overdue", Task.due_date < today))),
            ),
        ]

    async def _due_reminders(self):
        today = _today()
        kind = case((Task.due_date < today, "overdue"), else_="due_soon")
        already_sent = exists().where(Notice.ticket_id == Task.id, Notice.recipient_id == self.auth.user.id, Notice.kind == kind, Notice.due_date == Task.due_date)
        tasks = (await self.db.execute(select(Task).where(Task.assigned_id == self.auth.user.id, Task.is_deleted.is_(False), Task.status.in_([0, 1]), Task.due_date <= today + timedelta(days=1), ~already_sent).order_by(Task.due_date, Task.id).limit(100))).scalars().all()
        for task in tasks:
            kind_value = "overdue" if task.due_date < today else "due_soon"
            message = f"任务已逾期（截止日期 {task.due_date}），请及时跟进" if kind_value == "overdue" else f"任务临近截止（截止日期 {task.due_date}）"
            try:
                async with self.db.begin_nested():
                    self.db.add(Notice(recipient_id=self.auth.user.id, ticket_id=task.id, kind=kind_value, message=message, due_date=task.due_date, dedup_key=f"{task.id}:{self.auth.user.id}:{kind_value}:{task.due_date}"))
                    await self.db.flush()
            except IntegrityError:
                # 多标签页或多进程同时检查，由唯一键保证只产生一条提醒。
                pass

    async def unread(self):
        await self._due_reminders()
        return await self.db.scalar(select(func.count()).select_from(Notice).join(Task, Task.id == Notice.ticket_id).where(*(await self._conditions()), Notice.is_read.is_(False))) or 0

    async def inbox(self, page: int, size: int):
        unread = await self.unread()
        conditions = await self._conditions()
        total = await self.db.scalar(select(func.count()).select_from(Notice).join(Task, Task.id == Notice.ticket_id).where(*conditions)) or 0
        rows = (await self.db.execute(select(Notice, Task.title).join(Task, Task.id == Notice.ticket_id).where(*conditions).order_by(Notice.id.desc()).offset((page-1)*size).limit(size))).all()
        return {"unread": unread, "total": total, "items": [{"id": n.id, "ticket_id": n.ticket_id, "title": title, "kind": n.kind, "message": n.message, "is_read": n.is_read, "created_time": n.created_time} for n, title in rows]}

    async def mark_read(self, notice_id: int | None):
        ids = select(Notice.id).join(Task, Task.id == Notice.ticket_id).where(*(await self._conditions()))
        if notice_id is not None:
            ids = ids.where(Notice.id == notice_id)
        # 先取自己有权读取的消息 ID，兼容 MySQL 更新表不能直接引用自身子查询的限制。
        values = (await self.db.execute(ids)).scalars().all()
        if not values:
            return False
        await self.db.execute(update(Notice).where(Notice.id.in_(values), Notice.recipient_id == self.auth.user.id).values(is_read=True))
        return True


NotificationRouter = APIRouter(prefix="/notifications", tags=["任务消息"])
TaskAuth = Annotated[AuthSchema, Security(AuthPermission(["module_system:ticket:query"]))]
TaskDB = Annotated[AsyncSession, Depends(db_getter)]


@NotificationRouter.get("", response_model=ResponseSchema[dict], summary="当前用户的任务消息")
async def task_notifications(auth: TaskAuth, db: TaskDB, page: Annotated[PaginationQueryParam, Depends()]):
    return SuccessResponse(data=await TaskNotificationService(auth, db).inbox(page.page_no, page.page_size))


@NotificationRouter.get("/unread-count", response_model=ResponseSchema[int], summary="当前用户未读任务消息数")
async def task_notification_count(auth: TaskAuth, db: TaskDB):
    return SuccessResponse(data=await TaskNotificationService(auth, db).unread())


@NotificationRouter.put("/read-all", response_model=ResponseSchema[None], summary="全部任务消息标记已读")
async def read_all_task_notifications(auth: TaskAuth, db: TaskDB):
    await TaskNotificationService(auth, db).mark_read(None)
    return SuccessResponse()


@NotificationRouter.put("/{notice_id}/read", response_model=ResponseSchema[None], summary="标记自己的任务消息已读")
async def read_task_notification(auth: TaskAuth, db: TaskDB, notice_id: Annotated[int, Path(ge=1)]):
    await TaskNotificationService(auth, db).mark_read(notice_id)
    return SuccessResponse()
