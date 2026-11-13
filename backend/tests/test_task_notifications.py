from datetime import date, timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema
from app.modules.system.user.model import UserModel
from app.modules.system.ticket.model import TicketModel
from app.modules.system.ticket.notifications import TaskNotificationService, notify_task


async def test_notifications_are_private_and_deadlines_deduplicated(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'messages.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            users = [UserModel(username=f"notice{i}", name=f"同事{i}", password="test") for i in range(3)]
            db.add_all(users); await db.flush()
            creator, owner, other = users
            task = TicketModel(title="交付资料", created_id=creator.id, assigned_id=owner.id, due_date=date.today()+timedelta(days=1))
            db.add(task); await db.flush()
            await notify_task(db, task, creator.id, "assigned", "任务已分配给你", recipients={owner.id})
            auth = AuthSchema(user={"id": owner.id})
            svc = TaskNotificationService(auth, db)
            first = await svc.inbox(1, 20)
            assert first["unread"] == 2
            second = await svc.inbox(1, 20)
            assert second["total"] == 2
            foreign = TaskNotificationService(AuthSchema(user={"id": other.id, "is_superuser": True}), db)
            assert (await foreign.inbox(1, 20))["total"] == 0
            assert not await foreign.mark_read(first["items"][0]["id"])
            assert await svc.mark_read(first["items"][0]["id"])
            assert (await svc.inbox(1, 20))["unread"] == 1
            task.status = 2; await db.flush()
            assert (await svc.inbox(1, 20))["total"] == 1  # 已完成任务不再显示临期警告
            await svc.mark_read(None)
            assert (await svc.inbox(1, 20))["unread"] == 0
            task.status = 0
            task.due_date = date.today() - timedelta(days=1)
            await db.flush()
            overdue = await svc.inbox(1, 20)
            assert overdue["unread"] == 1
            assert overdue["items"][0]["kind"] == "overdue"
            task.due_date = date.today() + timedelta(days=5)
            await db.flush()
            assert (await svc.inbox(1, 20))["unread"] == 0

            from app.modules.system.ticket.service import TicketService, TicketCommentService
            from app.modules.system.ticket.schema import TicketCommentCreateSchema, TicketUpdateSchema
            creator_auth = AuthSchema(user={"id": creator.id})
            await TicketCommentService(creator_auth, db).create(task.id, TicketCommentCreateSchema(content="补充交付要求"))
            assert (await svc.inbox(1, 20))["unread"] == 1
            assert (await TaskNotificationService(creator_auth, db).inbox(1, 20))["total"] == 0  # 不提醒自己
            await TicketService(auth, db).update(task.id, TicketUpdateSchema(status=1))
            assert (await TaskNotificationService(creator_auth, db).inbox(1, 20))["items"][0]["kind"] == "status"
            await TicketService(creator_auth, db).update(task.id, TicketUpdateSchema(assigned_id=other.id))
            assert (await foreign.inbox(1, 20))["items"][0]["kind"] == "assigned"
            assert (await svc.inbox(1, 20))["total"] == 0  # 转派后旧负责人失去任务访问权
            from sqlalchemy import select, func
            from app.modules.system.ticket.model import TaskNotificationModel
            before = await db.scalar(select(func.count()).select_from(TaskNotificationModel))
            with pytest.raises(RuntimeError):
                async with db.begin_nested():
                    temp = TicketModel(title="回滚的任务", created_id=creator.id, assigned_id=other.id)
                    db.add(temp); await db.flush()
                    await notify_task(db, temp, creator.id, "assigned", "不应留下的提醒", recipients={other.id})
                    raise RuntimeError("模拟任务提交失败")
            assert await db.scalar(select(func.count()).select_from(TaskNotificationModel)) == before
    finally:
        await engine.dispose()
