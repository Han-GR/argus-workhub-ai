from datetime import date
import pytest
from app.modules.system.ticket.meeting import resolve_deadline, normalize_extraction, RawExtraction, ConfirmMeeting


def test_relative_dates_are_resolved_from_meeting_date():
    base = date(2026, 11, 13)
    assert resolve_deadline("明天", base) == date(2026, 11, 14)
    assert resolve_deadline("下周五", base) == date(2026, 11, 20)
    assert resolve_deadline("2026-12-01", base) == date(2026, 12, 1)
    assert resolve_deadline("尽快", base) is None
    assert resolve_deadline("2026-02-30", base) is None


def test_ambiguous_owner_and_ungrounded_deadline_are_not_assigned():
    raw = RawExtraction.model_validate({"tasks": [{"title": "整理资料", "description": "归档资料", "owner_name": "小王", "due_text": "明天", "evidence": "小王整理资料"}]})
    users = [{"id": 1, "name": "小王", "username": "wang1"}, {"id": 2, "name": "小王", "username": "wang2"}]
    rows = normalize_extraction(raw, "小王整理资料，尽快完成。", date(2026, 11, 13), users)
    assert rows[0]["assigned_id"] is None
    assert rows[0]["due_date"] is None
    assert rows[0]["warnings"]
    assert rows[0]["evidence"] == "小王整理资料"


def test_explicit_confirmation_required():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ConfirmMeeting(confirmed=False, tasks=[{"title": "任务"}])


async def test_extract_confirm_receipt_and_transaction_rollback(tmp_path, monkeypatch):
    import json
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import AsyncMock
    from app.core.base_model import MappedBase
    from app.core.base_schema import AuthSchema
    from app.core.exceptions import CustomException
    import app.modules.system.ticket.meeting as module
    from app.modules.system.ticket.model import TicketModel, TaskNotificationModel, MeetingTaskDraftModel
    from app.modules.system.user.model import UserModel

    response = json.dumps({"tasks": [{"title": "整理资料", "description": "整理本周资料", "owner_name": "韩工", "due_text": "下周五", "evidence": "韩工下周五整理资料"}]})
    complete = AsyncMock(return_value=response)
    monkeypatch.setattr(module.AgnoFactory, "complete_json", complete)
    monkeypatch.setattr(module, "get_user_model_config", AsyncMock(return_value=None))
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'meetings.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            creator = UserModel(username="meeting_creator", name="创建人", password="test")
            owner = UserModel(username="han", name="韩工", password="test")
            db.add_all([creator, owner]); await db.flush()
            auth = AuthSchema(user={"id": creator.id})
            service = module.MeetingTaskService(auth, db)
            source = module.ExtractMeeting(source_text="会议记录：韩工下周五整理资料，交给项目负责人。", reference_date="2026-11-13")
            draft = await service.extract(source, None)
            assert await db.scalar(select(func.count()).select_from(TicketModel)) == 0
            assert draft["tasks"][0]["assigned_id"] == owner.id
            assert draft["tasks"][0]["due_date"] == "2026-11-20"
            confirm = module.ConfirmMeeting(confirmed=True, tasks=[{"title": "整理资料", "assigned_id": owner.id, "due_date": "2026-11-20"}])
            first = await service.confirm(draft["id"], confirm)
            again = await service.confirm(draft["id"], confirm)
            assert first["task_ids"] == again["task_ids"] and again["replayed"]
            assert await db.scalar(select(func.count()).select_from(TicketModel)) == 1
            assert await db.scalar(select(func.count()).select_from(TaskNotificationModel)) == 1
            task = await db.get(TicketModel, first["task_ids"][0])
            assert task.source_meeting_id == draft["id"] and task.source_item_index == 0
            with pytest.raises(CustomException):
                await service.confirm(draft["id"], module.ConfirmMeeting(confirmed=True, tasks=[{"title": "不同任务"}]))
            other = module.MeetingTaskService(AuthSchema(user={"id": owner.id}), db)
            with pytest.raises(CustomException):
                await other._get(draft["id"])
            recovered = await service.extract(module.ExtractMeeting(**(source.model_dump() | {"draft_id": draft["id"]})), None)
            assert recovered["confirmed"] and complete.await_count == 1
            second_draft = await service.extract(source, None)
            with pytest.raises(CustomException):
                async with db.begin_nested():
                    await service.confirm(second_draft["id"], module.ConfirmMeeting(confirmed=True, tasks=[{"title": "应回滚的任务", "assigned_id": owner.id}, {"title": "无效负责人", "assigned_id": 99999}]))
            assert await db.scalar(select(func.count()).select_from(TicketModel)) == 1
            assert await db.scalar(select(func.count()).select_from(TaskNotificationModel)) == 1
            stored = await db.get(MeetingTaskDraftModel, second_draft["id"])
            await db.refresh(stored)
            assert stored.confirmed_hash is None and stored.created_task_ids is None
            complete.return_value = "不是JSON"
            fallback = await service.extract(source, None)
            assert fallback["tasks"] == [] and fallback["warnings"]
            assert complete.await_count == 4
            manual = await service.confirm(fallback["id"], module.ConfirmMeeting(confirmed=True, tasks=[{"title": "手动补充任务"}]))
            assert len(manual["task_ids"]) == 1
            complete.side_effect = TimeoutError()
            timeout = await service.extract(source, None)
            assert timeout["tasks"] == [] and timeout["warnings"]
    finally:
        await engine.dispose()


def test_extraction_requires_both_permissions(test_client, monkeypatch):
    from app.core.base_schema import AuthSchema
    from app.core.dependencies import get_current_user
    import app.modules.system.ticket.meeting as module
    from unittest.mock import AsyncMock
    monkeypatch.setattr(module.MeetingTaskService, "extract", AsyncMock(return_value={"tasks": []}))
    try:
        for permissions in [["module_system:ticket:create"], ["module_ai:chat:query"]]:
            test_client.app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1}, permissions=permissions)
            result = test_client.post("/system/ticket/meeting-drafts/extract", json={"source_text": "会议记录：明天整理客户资料。"})
            assert result.status_code == 403
        test_client.app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1}, permissions=["module_system:ticket:create", "module_ai:chat:query"])
        result = test_client.post("/system/ticket/meeting-drafts/extract", json={"source_text": "会议记录：明天整理客户资料。"})
        assert result.status_code == 200
        assert result.json()["msg"] == ""
    finally:
        test_client.app.dependency_overrides.pop(get_current_user, None)


def test_additive_meeting_migration_preserves_existing_tasks():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_13_1500_6a7b8c9d0e12.py"
    spec = importlib.util.spec_from_file_location("meeting_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE sys_ticket (id INTEGER PRIMARY KEY, title VARCHAR(200))"))
        conn.execute(sa.text("INSERT INTO sys_ticket VALUES (1, 'existing')"))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        assert conn.execute(sa.text("SELECT title, source_meeting_id, source_item_index FROM sys_ticket")).one() == ("existing", None, None)
        assert any(i["name"] == "uq_task_meeting_item" and i["unique"] for i in sa.inspect(conn).get_indexes("sys_ticket"))
    engine.dispose()


def test_extraction_failure_messages_are_specific():
    from app.modules.system.ticket.meeting import extraction_error_message
    assert "超时" in extraction_error_message(TimeoutError())
    assert "截断" in extraction_error_message(ValueError("AI_OUTPUT_INCOMPLETE"))
    assert "API Key" in extraction_error_message(RuntimeError("AI_MODEL_NOT_CONFIGURED"))


async def test_deepseek_extraction_disables_thinking_without_affecting_other_providers(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import openai
    from app.utils.ai_factory import AgnoFactory
    create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"tasks":[]}'))]))
    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    factory = AgnoFactory()
    await factory.complete_json("返回JSON", "测试文本", {"base_url": "https://api.deepseek.com/v1", "api_key": "fake-test-key", "model_id": "deepseek-v4-pro"})
    assert create.call_args.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}
    await factory.complete_json("返回JSON", "测试文本", {"base_url": "https://example.com/v1", "api_key": "fake-test-key", "model_id": "custom"})
    assert "extra_body" not in create.call_args.kwargs
    assert "response_format" not in create.call_args.kwargs
