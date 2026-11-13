import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import BackgroundTasks
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.vector_stores.types import VectorStoreQueryResult
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.ai.knowledge import service as module
from app.modules.ai.knowledge.controller import QuestionInput
from app.modules.system.dept.model import DeptModel
from app.modules.system.user.model import UserModel

CONFIG = {"base_url": "https://api.siliconflow.cn/v1", "model_id": "BAAI/bge-m3", "dimensions": 1024, "api_key": "secret"}


def test_vector_store_uses_database_zero_without_changing_application_redis(monkeypatch):
    from redis.exceptions import ResponseError

    application_uri = module.settings.REDIS_URI
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    connect = Mock(return_value=client)
    monkeypatch.setattr(module.SyncRedis, "from_url", connect)
    with module.vector_store("test-base", "fingerprint", 1024):
        pass
    uri = connect.call_args.args[0]
    assert urlsplit(uri).path == "/0"
    assert urlsplit(uri).netloc == urlsplit(application_uri).netloc
    assert module.settings.REDIS_URI == application_uri
    # Reusing an existing index remains valid; real Redis errors must still propagate.
    client.execute_command.side_effect = ResponseError("Index already exists")
    with module.vector_store("test-base", "fingerprint", 1024):
        pass
    client.execute_command.side_effect = ResponseError("Permission denied")
    with pytest.raises(ResponseError, match="Permission denied"):
        with module.vector_store("test-base", "fingerprint", 1024):
            pass


@pytest.fixture
async def library(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'knowledge.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)
    monkeypatch.setattr(module, "read_embedding_config", AsyncMock(return_value=CONFIG.copy()))
    monkeypatch.setattr(module, "embed_texts", AsyncMock(side_effect=lambda config, texts: [[0.1] * config["dimensions"] for _ in texts]))
    monkeypatch.setattr(module, "write_vectors", Mock())
    monkeypatch.setattr(module, "delete_vectors", Mock())
    monkeypatch.setattr(module, "get_user_model_config", AsyncMock(return_value=None))
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add_all([DeptModel(id=10, name="研发部", code="DEV"), DeptModel(id=20, name="人事部", code="HR")])
        await db.flush()
        db.add_all([UserModel(id=1, username="rag_owner", name="Owner", password="test", dept_id=10), UserModel(id=2, username="rag_other", name="Other", password="test", dept_id=20)])
        await db.commit()
        service = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 10, "is_superuser": True}), db, None, BackgroundTasks())
        yield service
    await engine.dispose()


async def test_company_sharing_department_boundaries_and_maintenance(library):
    company = await library.create_base("公司制度", None)
    dev = await library.create_base("研发规范", 10)
    hr = await library.create_base("人事资料", 20)
    member = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 10}), library.db, None, BackgroundTasks())
    visible = await member.catalog()
    assert {b["id"] for b in visible["bases"]} == {company["id"], dev["id"]}
    assert not visible["can_create"] and not visible["can_configure"]
    with pytest.raises(CustomException):
        await member.get_base(hr["id"])
    for base_id in (company["id"], dev["id"]):
        with pytest.raises(CustomException):
            await member.upload(base_id, "a.txt", b"unauthorized")
    maintainer = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 10}, permissions=["module_ai:knowledge:department"]), library.db, None, BackgroundTasks())
    assert (await maintainer.catalog())["can_create"]
    await maintainer.upload(dev["id"], "a.txt", b"development guide")
    for dept_id in (None, 20):
        with pytest.raises(CustomException):
            await maintainer.create_base("forbidden", dept_id)
    transferred = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 20}), library.db, None, BackgroundTasks())
    with pytest.raises(CustomException):
        await transferred.documents(dev["id"])
    assert (await member.list_documents(company["id"])) == []
    company_doc = await library.upload(company["id"], "policy.txt", b"company policy")
    assert (await member.list_documents(company["id"]))[0]["id"] == company_doc["id"]
    assert (await transferred.list_documents(company["id"]))[0]["id"] == company_doc["id"]
    for action in (member.get_document, member.reindex, member.delete):
        with pytest.raises(CustomException):
            await action(hr["id"], company_doc["id"])
    # A caller cannot pair an accessible library with a document from another library.
    with pytest.raises(CustomException):
        await member.get_document(dev["id"], company_doc["id"])
    with pytest.raises(CustomException, match="先删除"):
        await library.delete_base(company["id"])
    await library.delete_base(hr["id"])
    assert hr["id"] not in {b["id"] for b in (await library.catalog())["bases"]}
    dept = await library.db.get(DeptModel, 10)
    dept.is_deleted = True
    await library.db.flush()
    assert dev["id"] not in {b["id"] for b in (await member.catalog())["bases"]}
    before = module.embed_texts.await_count
    with pytest.raises(CustomException):
        await member.ask(dev["id"], "不应检索停用部门资料")
    assert module.embed_texts.await_count == before


def test_menu_seed_exposes_knowledge_as_a_separate_top_level_page():
    menus = json.loads((Path(__file__).parents[1] / "sql/sys_menu.json").read_text())
    base = next(m for m in menus if m.get("route_name") == "Knowledge")
    assert base["route_path"] == "/knowledge" and base["component_path"] == "module_ai/knowledge/index"
    assert base["permission"] == "module_ai:knowledge:query" and not base["hidden"]
    assert {b["permission"] for b in base["children"]} == {"module_ai:knowledge:manage", "module_ai:knowledge:department"}


@pytest.fixture
async def base_id(library):
    return (await library.create_base("研发资料", 10))["id"]


@pytest.mark.parametrize("name,content", [("a.exe", b"a"), ("a.txt", b""), ("a.txt", b" " * 10), ("a.txt", b"\xff"), ("a.txt", b"a" * (module.MAX_FILE_BYTES + 1)), ("a.md", "字".encode() * 20001)])
def test_parser_rejects_invalid_documents(name, content):
    with pytest.raises(CustomException):
        module.parse_document(name, content)


def test_parser_normalizes_text_and_questions_reject_blank():
    assert module.parse_document("a.MD", b"\xef\xbb\xbf hello\x00 ") == "hello"
    for question in ["", "   ", "x" * 1001]:
        with pytest.raises(ValidationError):
            QuestionInput(question=question)
    assert module.model_fingerprint(CONFIG) == module.model_fingerprint(CONFIG | {"api_key": "rotated"})
    assert module.model_fingerprint(CONFIG) != module.model_fingerprint(CONFIG | {"dimensions": 512})


async def test_upload_ownership_staleness_and_write_failure_preserve_previous(library, base_id, monkeypatch):
    result = await library.upload(base_id, "handbook.md", "员工每年可享五天年假。".encode())
    assert result["chunk_count"] == 1 and not result["needs_reindex"]
    doc_id = result["id"]
    nodes = module.write_vectors.call_args.args[3]
    assert nodes[0].ref_doc_id == doc_id and len(nodes[0].embedding) == 1024
    other = module.KnowledgeService(AuthSchema(user={"id": 2}), library.db, None, BackgroundTasks())
    with pytest.raises(CustomException, match="无权访问"):
        await other.list_documents(base_id)
    for action in (other.get_document, other.delete, other.reindex):
        with pytest.raises(CustomException, match="无权访问"):
            await action(base_id, doc_id)
    monkeypatch.setattr(module, "read_embedding_config", AsyncMock(return_value=CONFIG | {"dimensions": 512}))
    assert (await library.list_documents(base_id))[0]["needs_reindex"]
    module.write_vectors.side_effect = RuntimeError("Search unavailable")
    with pytest.raises(CustomException, match="写入失败"):
        await library.reindex(base_id, doc_id)
    assert (await library.get_document(base_id, doc_id)).content == "员工每年可享五天年假。"
    module.delete_vectors.assert_not_called()
    module.write_vectors.side_effect = None
    replacement = await library.reindex(base_id, doc_id)
    assert replacement["id"] != doc_id
    assert not (await library.list_documents(base_id))[0]["needs_reindex"]
    await library.delete(base_id, replacement["id"])
    assert await library.documents(base_id) == []


async def test_rollback_never_deletes_vectors_for_committed_documents(library, base_id):
    doc_id = (await library.upload(base_id, "handbook.md", b"Annual leave is five days."))["id"]
    await library.db.commit()
    await library.reindex(base_id, doc_id)
    module.delete_vectors.assert_not_called()
    await library.db.rollback()
    assert (await library.get_document(base_id, doc_id)).name == "handbook.md"
    # Background work is only executed by the HTTP layer after a successful commit.
    library.background_tasks = BackgroundTasks()
    await library.delete(base_id, doc_id)
    module.delete_vectors.assert_not_called()
    await library.db.commit()
    await library.background_tasks()
    module.delete_vectors.assert_called_once()


async def test_ask_filters_foreign_sources_and_validates_citations(library, base_id, monkeypatch):
    doc_id = (await library.upload(base_id, "handbook.md", b"Annual leave is five days."))["id"]
    def node(owner_doc, text):
        return TextNode(text=text, relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=owner_doc)})
    retrieve = Mock(return_value=VectorStoreQueryResult(nodes=[node(doc_id, "Annual leave is five days."), node(str(uuid4()), "private foreign data")], similarities=[0.9, 0.8]))
    monkeypatch.setattr(module, "retrieve_vectors", retrieve)
    complete = AsyncMock(return_value=json.dumps({"answer": "年假五天 [1]", "citations": [1]}))
    monkeypatch.setattr(module.AgnoFactory, "complete_json", complete)
    answer = await library.ask(base_id, "年假几天？")
    assert answer["sources"] == [{"number": 1, "document_id": doc_id, "name": "handbook.md", "text": "Annual leave is five days.", "score": 0.9}]
    assert retrieve.call_args.args[0] == base_id and retrieve.call_args.args[-1] == [doc_id]
    assert "private foreign data" not in complete.call_args.args[1]
    complete.return_value = json.dumps({"answer": "无依据", "citations": [2]})
    with pytest.raises(CustomException, match="回答生成失败"):
        await library.ask(base_id, "年假几天？")
    complete.return_value = json.dumps({"answer": "不知道", "citations": []})
    assert (await library.ask(base_id, "年假几天？"))["sources"] == []
    retrieve.return_value = VectorStoreQueryResult(nodes=[], similarities=[])
    assert "未找到相关资料" in (await library.ask(base_id, "年假几天？"))["answer"]


async def test_missing_config_and_empty_library_do_not_call_models(library, base_id, monkeypatch):
    with pytest.raises(CustomException, match="没有可检索"):
        await library.ask(base_id, "问题")
    module.embed_texts.assert_not_awaited()
    monkeypatch.setattr(module, "read_embedding_config", AsyncMock(return_value=None))
    with pytest.raises(CustomException, match="配置知识库向量模型"):
        await library.upload(base_id, "a.txt", b"text")


async def test_http_commit_failure_keeps_old_vectors_and_success_cleans_them(library, base_id):
    import httpx
    from fastapi import FastAPI

    from app.core.dependencies import db_getter, get_current_user, redis_getter
    from app.core.exceptions import handle_exception
    from app.modules.ai.knowledge.controller import KnowledgeRouter

    doc_id = (await library.upload(base_id, "a.txt", b"knowledge"))["id"]
    await library.db.commit()
    app = FastAPI()
    handle_exception(app)
    app.include_router(KnowledgeRouter)
    fail_commit = True

    async def transaction():
        try:
            yield library.db
            if fail_commit:
                raise RuntimeError("commit failed")
            await library.db.commit()
        finally:
            await library.db.rollback()

    app.dependency_overrides[db_getter] = transaction
    app.dependency_overrides[redis_getter] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1, "dept_id": 10}, permissions=["module_ai:knowledge:query", "module_ai:knowledge:department"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        response = await client.post(f"/knowledge/bases/{base_id}/documents/{doc_id}/reindex")
        assert response.status_code == 500
        module.delete_vectors.assert_not_called()
        assert (await library.get_document(base_id, doc_id)).content == "knowledge"
        fail_commit = False
        response = await client.post(f"/knowledge/bases/{base_id}/documents/{doc_id}/reindex")
        assert response.status_code == 200
        module.delete_vectors.assert_called_once_with(base_id, module.model_fingerprint(CONFIG), 1024, doc_id)
        app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 2, "dept_id": 20}, permissions=["module_ai:knowledge:query"])
        assert (await client.get(f"/knowledge/bases/{base_id}/documents")).status_code == 404
        assert (await client.post(f"/knowledge/bases/{base_id}/documents", files={"file": ("a.txt", b"text")})).status_code == 404


async def test_shared_vector_configuration_is_admin_only_and_old_routes_are_removed(library):
    import httpx
    from fastapi import FastAPI
    from test_ai_embedding_config import MemoryRedis

    from app.core.dependencies import get_current_user, redis_getter
    from app.core.exceptions import handle_exception
    from app.modules.ai.chat.controller import ChatRouter
    from app.modules.ai.knowledge.controller import KnowledgeRouter

    app = FastAPI()
    handle_exception(app)
    app.include_router(KnowledgeRouter)
    app.include_router(ChatRouter, prefix="/chat")
    redis = MemoryRedis()
    app.dependency_overrides[redis_getter] = lambda: redis
    app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1}, permissions=["module_ai:knowledge:query", "module_ai:knowledge:manage"])
    paths = app.openapi()["paths"]
    assert "/chat/embedding" not in paths
    assert "/knowledge/documents" not in paths
    data = {"api_key": "company-secret", "dimensions": 256}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for method, path in [("GET", "/knowledge/embedding"), ("PUT", "/knowledge/embedding"), ("POST", "/knowledge/embedding/test")]:
            response = await client.request(method, path, json=data if method != "GET" else None)
            assert response.status_code == 403
        assert not redis.data
        app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1, "is_superuser": True})
        response = await client.put("/knowledge/embedding", json=data)
        assert response.status_code == 200 and response.json()["data"]["has_api_key"]
        assert "company-secret" not in response.text
        assert "company-secret" not in json.dumps(redis.data)
        # Reading admin configuration still never returns the secret.
        response = await client.get("/knowledge/embedding")
        assert "api_key" not in response.json()["data"]
        assert len(redis.data) == 1


@pytest.mark.parametrize("partial", [False, True])
def test_knowledge_migration_creates_company_schema_and_preserves_users(partial):
    from app.modules.system.menu.model import MenuModel
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_13_1700_8b9c0d1e2f34.py"
    spec = importlib.util.spec_from_file_location("knowledge_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE sys_dept (id INTEGER PRIMARY KEY)"))
        MenuModel.__table__.create(conn)
        conn.execute(sa.text("INSERT INTO sys_user VALUES (1)"))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        if partial:
            conn.execute(sa.text("CREATE TABLE ai_knowledge_base (id VARCHAR(36) PRIMARY KEY, name VARCHAR(100) NOT NULL, dept_id INTEGER REFERENCES sys_dept(id) ON DELETE RESTRICT, created_time DATETIME NOT NULL)"))
            conn.execute(sa.text("CREATE INDEX ix_ai_knowledge_base_dept_id ON ai_knowledge_base(dept_id)"))
            conn.execute(sa.text("ALTER TABLE ai_knowledge_document ADD COLUMN base_id VARCHAR(36) NOT NULL"))
            conn.execute(sa.text("ALTER TABLE ai_knowledge_document ADD COLUMN uploaded_by INTEGER"))
        spec = importlib.util.spec_from_file_location("company_knowledge_migration", path.with_name("2026_11_13_1822_360056454ecc.py"))
        enterprise = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(enterprise)
        enterprise.op = Operations(MigrationContext.configure(conn))
        enterprise.upgrade()
        assert conn.execute(sa.text("SELECT id FROM sys_user")).scalar() == 1
        assert sa.inspect(conn).has_table("ai_knowledge_base")
        columns = {c["name"] for c in sa.inspect(conn).get_columns("ai_knowledge_document")}
        assert "base_id" in columns and "owner_id" not in columns
        menu = conn.execute(sa.text("SELECT id, route_path, component_path FROM sys_menu WHERE route_name = 'Knowledge'")).one()
        assert menu[1:] == ("/knowledge", "module_ai/knowledge/index")
        permissions = conn.execute(sa.text("SELECT permission FROM sys_menu WHERE parent_id = :id"), {"id": menu[0]}).scalars().all()
        assert set(permissions) == {"module_ai:knowledge:manage", "module_ai:knowledge:department"}
    engine.dispose()
