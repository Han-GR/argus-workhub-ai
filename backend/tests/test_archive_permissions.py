from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.system.dept.model import DeptModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel
from app.modules.task.storage.browse.service import StorageFileService
from app.modules.task.storage.node.model import StorageNodeModel
from app.utils.import_util import ImportUtil


@pytest.fixture
async def archive(tmp_path):
    ImportUtil.find_models(MappedBase)
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        for i in (1, 2):
            db.add(DeptModel(id=i, name=f"部门{i}", code=f"D{i}"))
        perms = ["query", "department_manage", "manage_all", "upload", "download", "update", "delete"]
        for i, perm in enumerate(perms, 1):
            db.add(MenuModel(id=i, name=perm, type=3, order=i,
                             permission=f"module_task:storage:browse:{perm}"))
        for i, dept in [(1, 1), (2, 1), (3, 2), (4, None), (5, 1), (6, 2), (7, 2)]:
            db.add(UserModel(id=i, username=f"u{i}", name=f"用户{i}", password="test", dept_id=dept, is_superuser=i == 7))
            db.add(RoleModel(id=i, name=f"r{i}", code=f"R{i}", data_scope=1))
            db.add(UserRolesModel(user_id=i, role_id=i))
            for menu_id in (1, 4, 5, 6, 7):
                db.add(RoleMenusModel(role_id=i, menu_id=menu_id))
        db.add(RoleMenusModel(role_id=5, menu_id=2))
        db.add(RoleMenusModel(role_id=6, menu_id=3))
        db.add(StorageNodeModel(id=1, name="档案", protocol="local", host=str(tmp_path), port=0, is_default=True))
        await db.flush()
        # 故意不提供部门及权限缓存，服务必须以数据库为准。
        service = lambda user: StorageFileService(AuthSchema(user={"id": user}), db)
        yield db, service, tmp_path
    await engine.dispose()


def file(name="a.txt", data=b"hello"):
    return UploadFile(filename=name, file=BytesIO(data))


async def names(service, prefix=""):
    return {entry["name"] for entry in await service.list_files(1, prefix)}


async def test_visibility_matrix_and_no_superuser_override(archive):
    _, service, root = archive
    for scope in ("private", "department", "company"):
        result = await service(1).upload(1, file(f"{scope}.txt"), f"{scope}.txt", visibility=scope)
        assert result.file_url is None
    assert await names(service(1)) == {"private.txt", "department.txt", "company.txt"}
    assert await names(service(2)) == {"department.txt", "company.txt"}
    assert await names(service(3)) == {"company.txt"}
    assert await names(service(4)) == {"company.txt"}
    assert await names(service(7)) == {"company.txt"}
    for user in (2, 3, 7):
        with pytest.raises(CustomException):
            await service(user).download(1, "private.txt")
    with pytest.raises(CustomException):
        await service(4).upload(1, file(), visibility="department")
    assert not (root / "company.txt").exists()


async def test_ownership_and_explicit_management_scopes(archive):
    _, service, _ = archive
    await service(1).upload(1, file(), "a.txt", visibility="department")
    for user in (2, 3, 7):
        with pytest.raises(CustomException):
            await service(user).delete(1, "a.txt")
    await service(5).rename(1, "a.txt", "renamed.txt")
    await service(6).delete(1, "renamed.txt")
    await service(1).upload(1, file(), "private.txt", visibility="private")
    with pytest.raises(CustomException):
        await service(5).delete(1, "private.txt")


async def test_folder_inheritance_subtree_guard_and_filtered_zip(archive):
    _, service, _ = archive
    await service(1).mkdir(1, "部门资料", visibility="department")
    await service(2).upload(1, file(), "部门资料/a.txt", visibility="company")
    assert await names(service(3)) == set()
    assert await names(service(2), "部门资料") == {"a.txt"}
    for operation in (
        lambda: service(1).delete(1, "部门资料"),
        lambda: service(1).rename(1, "部门资料", "新目录"),
        lambda: service(1).set_visibility(1, "部门资料", "company"),
    ):
        with pytest.raises(CustomException):
            await operation()
    with pytest.raises(CustomException):
        await service(3).download_dir(1, "部门资料")
    path, _ = await service(2).download_dir(1, "部门资料")
    import zipfile
    with zipfile.ZipFile(path) as zipped:
        assert zipped.read("部门资料/a.txt") == b"hello"
    Path(path).unlink()
    await service(5).set_visibility(1, "部门资料", "company")
    assert await names(service(3), "部门资料") == {"a.txt"}


async def test_no_overwrite_copy_move_and_anonymous_share(archive):
    _, service, _ = archive
    await service(1).upload(1, file(), "a.txt", visibility="company")
    with pytest.raises(CustomException):
        await service(2).upload(1, file(data=b"overwrite"), "a.txt")
    with pytest.raises(CustomException):
        await service(2).copy_or_move(1, "a.txt", 1, "b.txt", move=True)
    await service(2).copy_or_move(1, "a.txt", 1, "b.txt")
    await service(2).delete(1, "b.txt")
    with pytest.raises(CustomException):
        await service(1).share(1, "a.txt")
    with pytest.raises(CustomException):
        await service(1).rename(1, "a.txt", "../escape.txt")
    path, _ = await service(1).download(1, "a.txt")
    assert Path(path).read_bytes() == b"hello"
    Path(path).unlink()


async def test_department_changes_and_permission_revocation_take_effect(archive):
    db, service, _ = archive
    await service(1).upload(1, file(), "dept.txt", visibility="department")
    user = await db.get(UserModel, 2)
    user.dept_id = 2
    await db.flush()
    assert await names(service(2)) == set()
    await db.execute(delete(RoleMenusModel).where(RoleMenusModel.role_id == 1))
    with pytest.raises(CustomException):
        await service(1).list_files(1)


async def test_scope_inheritance_copy_and_pagination_never_expose_private_entries(archive):
    _, service, _ = archive
    await service(1).mkdir(1, "public", visibility="company")
    await service(1).mkdir(1, "secret", visibility="private")
    await service(1).upload(1, file(), "secret/a.txt")
    with pytest.raises(CustomException):
        await service(2).copy_or_move(1, "secret/a.txt", 1, "public/leak.txt")
    await service(1).rename(1, "secret/a.txt", "public/shared.txt")
    assert await names(service(2), "public") == {"shared.txt"}
    with pytest.raises(CustomException):
        await service(1).set_visibility(1, "public/shared.txt", "private")
    page = await service(2).list_files(1, page_size=1)
    assert [e["name"] for e in page["items"]] == ["public"]
    assert page["has_next"] is False


async def test_raw_transfer_requires_explicit_cross_department_permission(archive):
    db, _, _ = archive
    from app.modules.task.storage.transfer.service import StorageTransferService
    for user in (1, 5, 7):
        with pytest.raises(CustomException):
            await StorageTransferService(AuthSchema(user={"id": user}), db)._check_archive_transfer_access()
    with pytest.raises(CustomException):
        await StorageTransferService(AuthSchema(user={"id": 6}), db)._check_archive_transfer_access()
    db.add(MenuModel(id=8, name="存储配置", type=3, order=8, permission="module_task:storage:node:manage"))
    db.add(RoleMenusModel(role_id=6, menu_id=8))
    await db.flush()
    await StorageTransferService(AuthSchema(user={"id": 6}), db)._check_archive_transfer_access()


async def test_ai_listing_uses_the_same_acl(archive, monkeypatch):
    db, service, _ = archive
    from app.modules.ai.tools import registry
    await service(1).upload(1, file(), "secret.txt", visibility="department")
    await service(1).upload(1, file(), "public.txt", visibility="company")
    class Context:
        async def __aenter__(self): return db
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(registry, "async_db_session", Context)
    tools = {t.name: t.func for t in registry.build_readonly_tools(AuthSchema(user={"id": 3}))}
    result = await tools["storage_files"]("档案")
    assert [e["name"] for e in result["entries"]] == ["public.txt"]
    assert "host" not in (await tools["storage_sources"]())[0]


async def test_storage_config_is_separate_from_file_access(archive):
    db, _, _ = archive
    from app.modules.task.storage.node.permissions import require_storage_config_admin
    with pytest.raises(CustomException):
        await require_storage_config_admin(AuthSchema(user={"id": 1}), db)
    await require_storage_config_admin(AuthSchema(user={"id": 7}), db)


async def test_delete_does_not_destroy_data_before_transaction_commit(archive):
    db, service, root = archive
    await service(1).upload(1, file(), "a.txt")
    await db.commit()
    objects = list((root / "_argus_archive").iterdir())
    await service(1).delete(1, "a.txt")
    assert objects[0].read_bytes() == b"hello"
    await db.rollback()
    await db.commit()
    import asyncio
    await asyncio.sleep(0)
    assert objects[0].exists()
    local, _ = await service(1).download(1, "a.txt")
    assert Path(local).read_bytes() == b"hello"
    Path(local).unlink()


async def test_omitted_source_move_resolves_default_before_comparing_target(archive):
    db, service, root = archive
    db.add(StorageNodeModel(id=2, name="第二档案", protocol="local", host=str(root / "second"), port=0))
    await db.flush()
    await service(1).upload(1, file(), "a.txt")
    await service(1).copy_or_move(None, "a.txt", 2, "moved.txt", move=True)
    assert await names(service(1)) == set()
    assert [e["name"] for e in await service(1).list_files(2)] == ["moved.txt"]


async def test_upload_without_path_registers_original_name_and_never_returns_public_url(archive):
    _, service, _ = archive
    result = await service(1).upload(None, file("原文件.txt"))
    assert result.file_path == result.file_name == "原文件.txt"
    assert result.file_url is None
    assert await names(service(2)) == set()


async def test_failed_download_closes_adapter_and_removes_partial_temp(archive, monkeypatch):
    _, service, _ = archive
    await service(1).upload(1, file(), "a.txt")
    paths, closed = [], []
    class BadAdapter:
        async def download(self, key, temp):
            paths.append(Path(temp))
            Path(temp).write_text("partial")
            raise RuntimeError("provider unavailable")
        async def close(self): closed.append(True)
    reader = service(1)
    async def adapter(*args): return BadAdapter()
    monkeypatch.setattr(reader, "_get_adapter", adapter)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await reader.download(1, "a.txt")
    assert closed == [True] and not paths[0].exists()


async def test_bucket_selection_is_limited_to_the_configured_bucket(archive):
    db, service, _ = archive
    node = await db.get(StorageNodeModel, 1)
    node.bucket = "configured"
    await db.flush()
    await service(1).upload(1, file(), "a.txt", bucket="configured")
    await service(1).copy_or_move(1, "a.txt", 1, "b.txt", move=True, bucket="configured")
    assert await names(service(1)) == {"b.txt"}
    with pytest.raises(CustomException):
        await service(1).list_files(1, bucket="other")
