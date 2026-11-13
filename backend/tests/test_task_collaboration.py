from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from app.core.exceptions import CustomException
from app.modules.system.ticket.schema import TicketCreateSchema, TicketUpdateSchema, TicketQueryParam
from app.modules.system.ticket.service import TicketService


def service(uid=1, admin=False):
    return TicketService(SimpleNamespace(user=SimpleNamespace(id=uid, is_superuser=admin)), None)


def test_task_fields_and_validation():
    task = TicketCreateSchema(title="内部任务", assigned_id=2, priority=3, due_date="2026-12-01", attachment_url="/api/v1/static/upload/a.pdf")
    assert task.assigned_id == 2 and task.priority == 3 and task.due_date == date(2026, 12, 1)
    for payload in [{"priority": 4}, {"assigned_id": -1}, {"attachment_url": "javascript:alert(1)"}]:
        with pytest.raises(ValidationError):
            TicketCreateSchema(title="任务", **payload)
    assert TicketQueryParam(view="assigned").view == "assigned"
    with pytest.raises(ValidationError):
        TicketUpdateSchema(priority=None)


def test_task_status_and_edit_permissions():
    task = SimpleNamespace(status=0, created_id=1, assigned_id=2)
    service(2)._validate_status_transition(task, 1)
    service(2)._validate_status_transition(task, 0)  # 未改状态也可保存
    with pytest.raises(CustomException):
        service(3)._validate_status_transition(task, 1)
    with pytest.raises(CustomException):
        service(2)._validate_status_transition(task, 3)  # 取消由创建人管理
    task.status = 2
    service(1)._validate_status_transition(task, 1)  # 重新跟进


async def test_assignee_cannot_reassign(monkeypatch):
    import app.modules.system.ticket.service as module
    task = SimpleNamespace(status=1, created_id=1, assigned_id=2)
    monkeypatch.setattr(module, "TicketCRUD", lambda *a: SimpleNamespace(get_or_404=AsyncMock(return_value=task)))
    with pytest.raises(CustomException):
        await service(2).update(1, TicketUpdateSchema(assigned_id=3))


def test_personal_filter_uses_authenticated_identity():
    query = service(7)._search(TicketQueryParam(view="assigned", assigned_id=999))
    assert query["assigned_id"] == ("eq", 7)
    assert "view" not in query
    assert service(7)._search(TicketQueryParam(view="created"))["created_id"] == ("eq", 7)


async def test_assigned_task_visibility_and_shared_comments(tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.base_model import MappedBase
    from app.core.base_schema import AuthSchema
    from app.core.permission import Permission
    from app.modules.system.user.model import UserModel
    from app.modules.system.ticket.model import TicketModel, TicketCommentModel
    from app.modules.system.ticket.crud import TicketCRUD, TicketCommentCRUD
    from app.modules.system.ticket.service import TicketCommentService
    from app.modules.system.ticket.schema import TicketCommentCreateSchema

    monkeypatch.setattr(Permission, "_load_user_data_scopes", AsyncMock(return_value={1}))
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(MappedBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            users = [UserModel(username=f"task_user_{i}", name=f"同事{i}", password="test") for i in range(3)]
            db.add_all(users)
            await db.flush()
            creator, assignee, outsider = users
            task = TicketModel(title="跨同事任务", created_id=creator.id, assigned_id=assignee.id)
            unrelated = TicketModel(title="其他人的任务", created_id=outsider.id)
            db.add_all([task, unrelated])
            await db.flush()
            db.add(TicketCommentModel(ticket_id=task.id, content="创建人的进展", created_id=creator.id))
            await db.flush()
            auth = AuthSchema(user={"id": assignee.id})
            svc = TicketService(auth, db)
            assert (await svc.page(1, 10, TicketQueryParam(view="assigned"))).total == 1
            assert await TicketCRUD(auth, db).get(id=unrelated.id) is None
            assert await TicketCommentCRUD(auth, db).count(ticket_id=task.id) == 1
            await TicketCommentService(auth, db).create(task.id, TicketCommentCreateSchema(content="负责人跟进"))
            assert await TicketCommentCRUD(AuthSchema(user={"id": creator.id}), db).count(ticket_id=task.id) == 2
            with pytest.raises(CustomException):
                await TicketCommentService(AuthSchema(user={"id": outsider.id}), db).page(task.id, 1, 10)
            await svc.update(task.id, TicketUpdateSchema(status=1))
            await svc.update(task.id, TicketUpdateSchema(status=2, due_date=None))
            with pytest.raises(CustomException):
                await svc.delete([task.id])
    finally:
        await engine.dispose()


def test_existing_tasks_survive_additive_migration():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_13_1118_1d932f4d9ffe.py"
    spec = importlib.util.spec_from_file_location("task_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE sys_ticket (id INTEGER PRIMARY KEY, title VARCHAR(200))"))
        connection.execute(sa.text("INSERT INTO sys_ticket VALUES (1, 'existing')"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        row = connection.execute(sa.text("SELECT title, priority, due_date, attachment_url FROM sys_ticket")).one()
        assert tuple(row) == ("existing", 1, None, None)
    engine.dispose()


def test_task_http_roundtrip(test_client, auth_headers):
    owners = test_client.get("/system/ticket/assignees", headers=auth_headers)
    assert owners.status_code == 200
    uid = owners.json()["data"][0]["id"]
    response = test_client.post("/system/ticket/create", headers=auth_headers, json={"title": "内部交付任务", "assigned_id": uid, "priority": 3, "due_date": "2026-12-01", "attachment_url": "/api/v1/static/upload/spec.pdf"})
    assert response.status_code in (200, 201), response.text
    data = response.json()["data"]
    assert data["priority"] == 3 and data["assigned_id"] == uid and data["due_date"] == "2026-12-01"
    task_id = data["id"]
    detail = test_client.get(f"/system/ticket/detail/{task_id}", headers=auth_headers).json()["data"]
    assert detail["created_id"]
    update = test_client.put(f"/system/ticket/update/{task_id}", headers=auth_headers, json={"due_date": None})
    assert update.status_code == 200 and update.json()["data"]["due_date"] is None
    comment = test_client.post(f"/system/ticket/{task_id}/comments", headers=auth_headers, json={"content": "今日进展已同步"})
    assert comment.status_code in (200, 201), comment.text
