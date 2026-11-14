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
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel

CONFIG = {"base_url": "https://api.siliconflow.cn/v1", "model_id": "BAAI/bge-m3", "dimensions": 1024, "api_key": "secret"}


async def test_document_upload_scope_and_owner_are_independent_of_maintenance_roles(library):
    member = module.KnowledgeService(AuthSchema(user={"id": 2, "dept_id": 20}), library.db, None, BackgroundTasks())
    public = await member.upload("policy.txt", b"company policy", "company")
    private = await member.upload("hr.txt", b"HR only", "department")
    assert public["visibility"] == "company" and public["dept_id"] is None
    assert private["visibility"] == "department" and private["dept_id"] == 20
    assert public["can_edit"] and private["can_edit"]
    other = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 10, "is_superuser": True}), library.db, None, BackgroundTasks())
    assert {d["id"] for d in await other.list_documents()} == {public["id"]}
    for doc_id in (public["id"], private["id"]):
        with pytest.raises(CustomException):
            await other.delete(doc_id)
        with pytest.raises(CustomException):
            await other.reindex(doc_id)


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
        query_menu = MenuModel(name="知识库", permission="module_ai:knowledge:query", status=0)
        department_menu = MenuModel(name="本部门维护", permission="module_ai:knowledge:department", type=3, status=0)
        db.add_all([RoleModel(id=101, name="部门维护人", code="KNOWLEDGE_DEPT", menus=[query_menu, department_menu]),
                    RoleModel(id=102, name="普通成员", code="KNOWLEDGE_READER", menus=[query_menu])])
        await db.flush()
        db.add_all([UserRolesModel(user_id=1, role_id=101), UserRolesModel(user_id=2, role_id=102)])
        await db.commit()
        service = module.KnowledgeService(AuthSchema(user={"id": 1, "dept_id": 10, "is_superuser": True}), db, None, BackgroundTasks())
        yield service
    await engine.dispose()


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


def actor(library, user_id=2, dept_id=20, superuser=False):
    return module.KnowledgeService(AuthSchema(user={"id": user_id, "dept_id": dept_id, "is_superuser": superuser},
        permissions=["module_ai:knowledge:query", "module_ai:knowledge:manage", "module_ai:knowledge:department"]), library.db, None, BackgroundTasks())


async def test_visibility_lists_owner_only_mutations_and_metadata_updates(library):
    owner = actor(library)
    company = await owner.upload("public.txt", b"company policy", "company")
    private = await owner.upload("private.txt", b"HR private", "department")
    dev = actor(library, 1, 10, True)
    dev_private = await dev.upload("dev.txt", b"DEV private", "department")
    assert {d["id"] for d in await owner.list_documents()} == {company["id"], private["id"]}
    assert {d["id"] for d in await owner.list_documents("company")} == {company["id"]}
    assert {d["id"] for d in await owner.list_documents("department")} == {private["id"]}
    assert {d["id"] for d in await dev.list_documents()} == {company["id"], dev_private["id"]}
    for target in (company["id"], private["id"]):
        for action in (dev.delete, dev.reindex):
            with pytest.raises(CustomException):
                await action(target)
        with pytest.raises(CustomException):
            await dev.update(target, "hacked", "company")
    module.embed_texts.reset_mock()
    await owner.update(company["id"], "renamed", "department")
    module.embed_texts.assert_not_awaited()
    assert not await dev.list_documents("company")
    assert (await owner.get_document(company["id"])) .name == "renamed"
    await owner.delete(private["id"])
    assert private["id"] not in {d["id"] for d in await owner.list_documents()}


async def test_department_required_and_transfer_never_grants_qa_access(library):
    no_dept = actor(library, 2, None)
    with pytest.raises(CustomException, match="有效部门"):
        await no_dept.upload("a.txt", b"text", "department")
    await no_dept.upload("public.txt", b"public", "company")
    owner = actor(library)
    private = await owner.upload("hr.txt", b"private HR", "department")
    transferred = actor(library, 2, 10)
    assert private["id"] not in {d["id"] for d in await transferred.list_documents()}
    mine = await transferred.list_documents("mine")
    old = next(d for d in mine if d["id"] == private["id"])
    assert old["can_edit"] and not old["can_query"]
    module.embed_texts.reset_mock()
    await transferred.delete(private["id"])
    assert module.embed_texts.await_count == 0
    dept = await library.db.get(DeptModel, 20)
    dept.status = 1
    await library.db.flush()
    with pytest.raises(CustomException, match="有效部门"):
        await owner.upload("a.txt", b"text", "department")


async def test_replacement_failure_and_rollback_preserve_document_and_vectors(library):
    owner = actor(library)
    result = await owner.upload("a.txt", b"original text", "department")
    doc_id = result["id"]
    await library.db.commit()
    module.write_vectors.side_effect = RuntimeError("Search unavailable")
    with pytest.raises(CustomException, match="写入失败"):
        await owner.update(doc_id, "new", "company", "new.txt", b"replacement")
    assert (await owner.get_document(doc_id)).content == "original text"
    module.delete_vectors.assert_not_called()
    module.write_vectors.side_effect = None
    replaced = await owner.update(doc_id, "new", "company", "new.txt", b"replacement")
    assert replaced["id"] != doc_id and replaced["uploaded_by"] == 2
    module.delete_vectors.assert_not_called()
    await library.db.rollback()
    assert (await owner.get_document(doc_id)).content == "original text"
    owner.background_tasks = BackgroundTasks()
    await owner.delete(doc_id)
    await library.db.commit()
    await owner.background_tasks()
    module.delete_vectors.assert_called_once()


async def test_qa_filters_before_search_and_never_uses_foreign_department_sources(library, monkeypatch):
    hr = actor(library)
    dev = actor(library, 1, 10, True)
    public = await hr.upload("public.txt", b"public", "company")
    private = await hr.upload("hr.txt", b"HR secret", "department")
    permitted = await dev.upload("dev.txt", b"DEV allowed", "department")
    # Existing documents may retain their original physical index namespace.
    (await dev.get_document(permitted["id"])).index_namespace = "old-index"
    await library.db.flush()
    def node(doc_id, text):
        return TextNode(text=text, relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id)})
    def search(namespace, fingerprint, dimensions, vector, ids):
        assert private["id"] not in ids
        if namespace == "documents":
            return VectorStoreQueryResult(nodes=[node(public["id"], "public"), node(private["id"], "HR secret")], similarities=[0.8, 0.99])
        return VectorStoreQueryResult(nodes=[node(permitted["id"], "DEV allowed")], similarities=[0.9])
    search_mock = Mock(side_effect=search)
    monkeypatch.setattr(module, "retrieve_vectors", search_mock)
    complete = AsyncMock(return_value=json.dumps({"answer": "DEV allowed [1]", "citations": [1]}))
    monkeypatch.setattr(module.AgnoFactory, "complete_json", complete)
    result = await dev.ask("资料有什么？")
    assert result["sources"][0]["document_id"] == permitted["id"]
    assert "HR secret" not in complete.call_args.args[1]
    assert search_mock.call_count == 2
    complete.return_value = json.dumps({"answer": "bad", "citations": [99]})
    with pytest.raises(CustomException, match="回答生成失败"):
        await dev.ask("question")
    await hr.update(public["id"], "now HR only", "department")
    module.embed_texts.reset_mock()
    # Another department with no accessible documents must not reach search or completion.
    outsider = actor(library, 1, None, True)
    with pytest.raises(CustomException, match="没有可检索"):
        await outsider.ask("HR private question")
    module.embed_texts.assert_not_awaited()


async def test_missing_embedding_config(library, monkeypatch):
    monkeypatch.setattr(module, "read_embedding_config", AsyncMock(return_value=None))
    with pytest.raises(CustomException, match="配置知识库向量模型"):
        await actor(library).upload("a.txt", b"text", "company")


async def test_http_upload_edit_owner_guard_and_revoked_role(library):
    import httpx
    from fastapi import FastAPI

    from app.core.dependencies import db_getter, get_current_user, redis_getter
    from app.core.exceptions import handle_exception
    from app.modules.ai.knowledge.controller import KnowledgeRouter
    app = FastAPI()
    handle_exception(app)
    app.include_router(KnowledgeRouter)
    async def database():
        yield library.db
    app.dependency_overrides[db_getter] = database
    app.dependency_overrides[redis_getter] = lambda: None
    # Query-only role can upload; old cached maintenance privileges add no ownership rights.
    current = {"id": 2, "dept_id": 20}
    app.dependency_overrides[get_current_user] = lambda: AuthSchema(user=current, permissions=["module_ai:knowledge:query", "module_ai:knowledge:manage"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/knowledge/documents", files={"file": ("a.txt", b"text")}, data={"visibility": "department", "dept_id": 10})
        assert created.status_code == 200
        doc_id = created.json()["data"]["id"]
        assert created.json()["data"]["dept_id"] == 20
        assert (await client.post("/knowledge/documents", files={"file": ("a.txt", b"text")}, data={"visibility": "bad"})).status_code == 422
        updated = await client.put(f"/knowledge/documents/{doc_id}", data={"name": "renamed", "visibility": "company"})
        assert updated.status_code == 200 and updated.json()["data"]["name"] == "renamed"
        current.update(id=1, dept_id=10)
        listing = (await client.get("/knowledge/documents")).json()["data"]
        assert not listing[0]["can_edit"]
        assert (await client.delete(f"/knowledge/documents/{doc_id}")).status_code == 404
        assert (await client.put(f"/knowledge/documents/{doc_id}", data={"name": "hacked", "visibility": "company"})).status_code == 404
        assert (await client.post(f"/knowledge/documents/{doc_id}/reindex")).status_code == 404
        current.update(id=2, dept_id=20)
        reader_role = await library.db.get(RoleModel, 102)
        reader_role.status = 1
        await library.db.flush()
        assert (await client.get("/knowledge/documents")).status_code == 403


async def test_shared_vector_configuration_is_admin_only_and_old_routes_are_removed(library):
    import httpx
    from fastapi import FastAPI
    from test_ai_embedding_config import MemoryRedis

    from app.core.dependencies import db_getter, get_current_user, redis_getter
    from app.core.exceptions import handle_exception
    from app.modules.ai.chat.controller import ChatRouter
    from app.modules.ai.knowledge.controller import KnowledgeRouter

    app = FastAPI()
    handle_exception(app)
    app.include_router(KnowledgeRouter)
    app.include_router(ChatRouter, prefix="/chat")
    redis = MemoryRedis()
    async def database():
        yield library.db
    app.dependency_overrides[db_getter] = database
    app.dependency_overrides[redis_getter] = lambda: redis
    app.dependency_overrides[get_current_user] = lambda: AuthSchema(user={"id": 1}, permissions=["module_ai:knowledge:query", "module_ai:knowledge:manage"])
    paths = app.openapi()["paths"]
    assert "/chat/embedding" not in paths
    assert "/knowledge/documents" in paths
    assert "/knowledge/bases" not in paths
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


def test_document_visibility_migration_preserves_scope_owner_and_vector_namespace():
    from datetime import UTC, datetime

    engine = sa.create_engine("sqlite://")
    root = Path(__file__).parents[1] / "app/alembic/versions"
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("INSERT INTO sys_user VALUES (1)"))
        conn.execute(sa.text("CREATE TABLE sys_dept (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("INSERT INTO sys_dept VALUES (20)"))
        conn.execute(sa.text("CREATE TABLE sys_role_menus (role_id INTEGER, menu_id INTEGER)"))
        MenuModel.__table__.create(conn)
        def migration(filename):
            spec = importlib.util.spec_from_file_location(filename, root / filename)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.op = Operations(MigrationContext.configure(conn))
            return mod
        migration("2026_11_13_1700_8b9c0d1e2f34.py").upgrade()
        migration("2026_11_13_1822_360056454ecc.py").upgrade()
        metadata = sa.MetaData()
        bases = sa.Table("ai_knowledge_base", metadata, autoload_with=conn)
        documents = sa.Table("ai_knowledge_document", metadata, autoload_with=conn)
        now = datetime.now(UTC)
        for base_id, dept_id in [("public-index", None), ("private-index", 20)]:
            conn.execute(bases.insert().values(id=base_id, name=base_id, dept_id=dept_id, created_time=now))
            conn.execute(documents.insert().values(id=str(uuid4()), base_id=base_id, uploaded_by=1, name=base_id,
                content="retained text", fingerprint="retained-model", dimensions=1024, chunk_count=1, created_time=now))
        migration("2026_11_13_2000_4d5e6f7a8b90.py").upgrade()
        rows = conn.execute(sa.text("SELECT visibility, dept_id, uploaded_by, index_namespace, content, fingerprint FROM ai_knowledge_document ORDER BY visibility")).all()
        assert rows == [("company", None, 1, "public-index", "retained text", "retained-model"),
                        ("department", 20, 1, "private-index", "retained text", "retained-model")]
        assert not sa.inspect(conn).has_table("ai_knowledge_base")
        assert not conn.execute(sa.text("SELECT id FROM sys_menu WHERE permission IN ('module_ai:knowledge:manage', 'module_ai:knowledge:department')")).all()
    engine.dispose()


def test_visibility_migration_rejects_missing_scope_instead_of_publishing_document():
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_11_13_2000_4d5e6f7a8b90.py"
    spec = importlib.util.spec_from_file_location("visibility_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE ai_knowledge_base (id VARCHAR(36) PRIMARY KEY, dept_id INTEGER)"))
            conn.execute(sa.text("CREATE TABLE ai_knowledge_document (id VARCHAR(36) PRIMARY KEY, base_id VARCHAR(36))"))
            conn.execute(sa.text("CREATE TABLE sys_menu (id INTEGER PRIMARY KEY, permission VARCHAR(100))"))
            conn.execute(sa.text("CREATE TABLE sys_role_menus (menu_id INTEGER)"))
            conn.execute(sa.text("INSERT INTO ai_knowledge_document VALUES ('orphan', 'missing-base')"))
            migration.op = Operations(MigrationContext.configure(conn))
            with pytest.raises(RuntimeError, match="找不到所属知识库"):
                migration.upgrade()
    finally:
        engine.dispose()
