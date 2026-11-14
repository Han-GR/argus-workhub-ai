import asyncio
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.modules.system.dept.model import DeptModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel
from app.modules.task.storage.core.base import _OBJECT_STORE_PROTOCOLS, StorageAdapterConfig
from app.modules.task.storage.core.factory import StorageAdapterFactory
from app.modules.task.storage.node.model import StorageNodeModel
from app.modules.task.storage.node.service import StorageNodeService
from app.utils.upload_util import UploadUtil

from .model import ArchiveEntryModel
from .schema import StoragePathCreateSchema, StoragePathResultSchema, StorageUploadResultSchema

ARCHIVE_PREFIX = "_argus_archive"


class StorageFileService:
    """所有档案访问均先校验逻辑目录；绝不直接列出存储物理目录。"""

    _CLEANUP_TASKS: set[asyncio.Task] = set()

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth, self.db = auth, db

    @staticmethod
    def _validate_remote_path(remote_path: str) -> str:
        if not remote_path or not remote_path.strip():
            raise CustomException(msg="请提供文件路径")
        parts = [p for p in remote_path.replace("\\", "/").split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts) or "\x00" in remote_path or not parts or len("/".join(parts)) > 500:
            raise CustomException(msg="非法的文件路径")
        return "/".join(parts)

    async def _context(self):
        user = await self.db.get(UserModel, self.auth.user.id)
        if not user or user.is_deleted or user.status != 0:
            raise CustomException(msg="账号不可用")
        self._user_id = user.id
        self._superuser = user.is_superuser
        dept = await self.db.get(DeptModel, user.dept_id) if user.dept_id else None
        self._dept_id = dept.id if dept and not dept.is_deleted and dept.status == 0 else None
        self._permissions = set((await self.db.scalars(select(MenuModel.permission)
            .join(RoleMenusModel, RoleMenusModel.menu_id == MenuModel.id)
            .join(RoleModel, RoleModel.id == RoleMenusModel.role_id)
            .join(UserRolesModel, UserRolesModel.role_id == RoleModel.id)
            .where(UserRolesModel.user_id == user.id, RoleModel.status == 0, RoleModel.is_deleted.is_(False),
                   MenuModel.status == 0, MenuModel.is_deleted.is_(False)))).all())
        if not user.is_superuser and "module_task:storage:browse:query" not in self._permissions:
            raise CustomException(msg="没有档案文件访问权限")

    async def sources(self):
        await self._context()
        nodes = (await self.db.scalars(select(StorageNodeModel).where(
            StorageNodeModel.status == 0, StorageNodeModel.is_deleted.is_(False)).order_by(StorageNodeModel.id))).all()
        return [{"id": n.id, "name": n.name, "protocol": n.protocol, "bucket": n.bucket,
                 "is_default": n.is_default, "status": n.status} for n in nodes]

    async def _source(self, source_id, bucket=None, lock=False):
        query = select(StorageNodeModel).where(StorageNodeModel.status == 0, StorageNodeModel.is_deleted.is_(False))
        if source_id:
            query = query.where(StorageNodeModel.id == source_id)
        query = query.order_by(StorageNodeModel.is_default.desc(), StorageNodeModel.id).limit(1)
        if lock:
            query = query.with_for_update()
        node = (await self.db.scalars(query)).first()
        if not node or (bucket and bucket != node.bucket):
            raise CustomException(msg="存储源或存储桶不可用")
        return node

    async def _get_source(self, source_id: int | None) -> StorageAdapterConfig:
        return StorageNodeService._build_config(await self._source(source_id))

    async def _get_adapter(self, source_id, bucket=None):
        node = await self._source(source_id, bucket)
        return StorageAdapterFactory.create(StorageNodeService._build_config(node))

    async def _prepare(self, source_id, bucket=None, lock=False, action="query"):
        await self._context()
        if not self._superuser and f"module_task:storage:browse:{action}" not in self._permissions:
            raise CustomException(msg="没有执行此文件操作的权限")
        self._node = await self._source(source_id, bucket, lock)
        self._bucket = self._node.bucket or ""
        # shortcut: 单个存储源目录在内存中解析继承关系，目录超过万条时改为递归 SQL 查询。
        self._entries = {e.path: e for e in (await self.db.scalars(select(ArchiveEntryModel).where(
            ArchiveEntryModel.source_id == self._node.id, ArchiveEntryModel.bucket == self._bucket))).all()}
        owners = {e.owner_id for e in self._entries.values() if e.owner_id is not None}
        self._owner_names = dict((await self.db.execute(select(UserModel.id, UserModel.name).where(UserModel.id.in_(owners)))).all()) if owners else {}

    def _root(self, entry):
        return self._entries[entry.path.split("/", 1)[0]]

    def _readable(self, entry):
        root = self._root(entry)
        return ("module_task:storage:browse:manage_all" in self._permissions or root.visibility == "company"
                or (root.visibility == "private" and root.owner_id == self._user_id)
                or (root.visibility == "department" and self._dept_id is not None and root.dept_id == self._dept_id))

    def _manageable(self, entry):
        return self._readable(entry) and (entry.owner_id == self._user_id
            or "module_task:storage:browse:manage_all" in self._permissions
            or ("module_task:storage:browse:department_manage" in self._permissions
                and self._dept_id is not None and entry.dept_id == self._dept_id
                and self._root(entry).visibility != "private"))

    def _require(self, path, manage=False):
        entry = self._entries.get(path)
        if not entry or not (self._manageable(entry) if manage else self._readable(entry)):
            raise CustomException(msg="文件不存在或没有访问权限")
        return entry

    def _subtree(self, entry, manage=False):
        entries = [e for p, e in self._entries.items() if p == entry.path or p.startswith(entry.path + "/")]
        if not all(self._manageable(e) if manage else self._readable(e) for e in entries):
            raise CustomException(msg="目录包含无权操作的文件")
        return entries

    def _destination(self, path):
        if path in self._entries:
            raise CustomException(msg="目标路径已存在，请使用其他名称")
        parent_path = path.rpartition("/")[0]
        parent = self._require(parent_path) if parent_path else None
        if parent and not parent.is_dir:
            raise CustomException(msg="目标不是文件夹")
        return parent

    def _scope(self, visibility):
        if visibility not in ("private", "department", "company"):
            raise CustomException(msg="无效的共享范围")
        if visibility == "department" and self._dept_id is None:
            raise CustomException(msg="没有有效部门，只能选择仅自己或全公司可见")

    def _new_entry(self, path, parent, visibility, is_dir, size=None, object_key=None):
        if not parent:
            self._scope(visibility)
        entry = ArchiveEntryModel(source_id=self._node.id, bucket=self._bucket, path=path,
            parent_id=parent.id if parent else None, visibility=visibility, is_dir=is_dir,
            owner_id=self._user_id, dept_id=self._dept_id, size=size, object_key=object_key)
        self.db.add(entry)
        return entry

    def _out(self, entry):
        root = self._root(entry)
        return {"name": Path(entry.path).name, "key": entry.path, "is_dir": entry.is_dir, "size": entry.size,
                "modified_time": entry.created_time, "visibility": root.visibility, "dept_id": root.dept_id,
                "owner_id": entry.owner_id, "owner_name": self._owner_names.get(entry.owner_id), "can_manage": self._manageable(entry), "inherited": entry.parent_id is not None}

    @staticmethod
    async def _save_to_temp(file: UploadFile, suffix: str = "") -> str:
        """将上传文件内容落盘到系统临时目录，返回临时路径。"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            async with aiofiles.open(path, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    await f.write(chunk)
        except Exception:
            os.unlink(path)
            raise
        finally:
            await file.seek(0)
        return path

    @staticmethod
    def _zip_directory(src_root: Path, zip_path: str, arc_root: Path) -> None:
        """把 src_root 下所有文件打包到 zip_path（相对于 arc_root 计算归档名）。

        ZIP_DEFLATED 是纯 CPU + 磁盘 IO 的同步操作，目录较大时会在事件循环里
        独占数秒，因此统一由调用方通过 asyncio.to_thread 在线程中执行。
        """
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in src_root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(arc_root).as_posix())

    async def upload(self, source_id, file, remote_path=None, bucket=None, visibility="private"):
        if not file or not file.filename:
            raise CustomException(msg="请选择要上传的文件")
        if not UploadUtil.check_path_traversal(file.filename):
            raise CustomException(msg="文件名包含非法字符")
        extension = UploadUtil.get_extension_from_filename(file.filename)
        if not extension or UploadUtil.is_dangerous_extension(extension):
            raise CustomException(msg="不允许上传此类型的文件")
        UploadUtil.check_file_size(file)
        target = remote_path or file.filename
        if target.endswith("/"):
            target += file.filename
        elif not target.lower().endswith(extension.lower()):
            target += extension
        target = self._validate_remote_path(target)
        await self._prepare(source_id, bucket, lock=True, action="upload")
        parent = self._destination(target)
        if not parent:
            self._scope(visibility)
        temp = await self._save_to_temp(file, suffix=extension)
        adapter = None
        key = f"{ARCHIVE_PREFIX}/{uuid4().hex}{extension}"
        try:
            adapter = await self._get_adapter(self._node.id)
            await adapter.upload(temp, key)
            self._new_entry(target, parent, visibility, False, os.path.getsize(temp), key)
            await self.db.flush()
        except Exception:
            if adapter:
                try:
                    await adapter.delete(key)
                except Exception:
                    logger.exception("档案上传失败后清理对象失败: {}", key)
            raise
        finally:
            try:
                if adapter:
                    await adapter.close()
            finally:
                os.unlink(temp)
        return StorageUploadResultSchema(file_path=target, file_name=Path(target).name, origin_name=file.filename, file_url=None)

    async def list_files(self, source_id, prefix="", bucket=None, page_size=None, cursor=None):
        await self._prepare(source_id, bucket)
        prefix = self._validate_remote_path(prefix) if prefix else ""
        parent = self._require(prefix) if prefix else None
        if parent and not parent.is_dir:
            raise CustomException(msg="该路径不是文件夹")
        entries = [e for e in self._entries.values() if e.parent_id == (parent.id if parent else None) and self._readable(e)]
        entries.sort(key=lambda e: (not e.is_dir, e.path))
        if page_size is None:
            return [self._out(e) for e in entries]
        try:
            offset = int(cursor or "0")
            if offset < 0 or page_size < 1 or page_size > 500:
                raise ValueError()
        except (ValueError, TypeError):
            raise CustomException(msg="无效的分页参数") from None
        items = [self._out(e) for e in entries[offset:offset + page_size]]
        has_next = offset + page_size < len(entries)
        return {"items": items, "has_next": has_next, "next_cursor": str(offset + page_size) if has_next else None}

    async def download(self, source_id, remote_path, bucket=None):
        await self._prepare(source_id, bucket, action="download")
        entry = self._require(self._validate_remote_path(remote_path))
        if entry.is_dir:
            raise CustomException(msg="请使用目录打包下载")
        fd, temp = tempfile.mkstemp(suffix=Path(entry.path).suffix)
        os.close(fd)
        adapter = await self._get_adapter(self._node.id)
        try:
            await adapter.download(entry.object_key, temp)
        except Exception:
            os.unlink(temp)
            raise
        finally:
            await adapter.close()
        return temp, Path(entry.path).name

    async def download_dir(self, source_id, remote_path, bucket=None):
        await self._prepare(source_id, bucket, action="download")
        entry = self._require(self._validate_remote_path(remote_path))
        if not entry.is_dir:
            raise CustomException(msg="该路径不是文件夹")
        entries = self._subtree(entry)
        tmp_root = tempfile.mkdtemp(prefix="archive_zip_")
        adapter = await self._get_adapter(self._node.id)
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        try:
            base = Path(tmp_root) / Path(entry.path).name
            base.mkdir()
            for child in entries:
                if not child.is_dir:
                    local = base / child.path[len(entry.path) + 1:]
                    local.parent.mkdir(parents=True, exist_ok=True)
                    await adapter.download(child.object_key, str(local))
            await asyncio.to_thread(self._zip_directory, base, zip_path, Path(tmp_root))
        except Exception:
            os.unlink(zip_path)
            raise
        finally:
            await adapter.close()
            await asyncio.to_thread(shutil.rmtree, tmp_root, ignore_errors=True)
        return zip_path, f"{Path(entry.path).name}.zip"

    async def delete(self, source_id, remote_path, bucket=None):
        await self._prepare(source_id, bucket, lock=True, action="delete")
        entry = self._require(self._validate_remote_path(remote_path), manage=True)
        entries = self._subtree(entry, manage=True)
        config = StorageNodeService._build_config(self._node)
        keys = [child.object_key for child in entries if child.object_key]
        for child in sorted(entries, key=lambda e: len(e.path), reverse=True):
            await self.db.delete(child)
            await self.db.flush()
        # 先提交权限元数据再删除物理对象，事务失败时原文件仍然完整。
        @event.listens_for(self.db.sync_session, "after_commit", once=True)
        def cleanup_after_commit(_session):
            event.remove(self.db.sync_session, "after_rollback", cancel_cleanup)
            task = asyncio.create_task(self._delete_objects(config, keys))
            self._CLEANUP_TASKS.add(task)
            task.add_done_callback(self._CLEANUP_TASKS.discard)

        @event.listens_for(self.db.sync_session, "after_rollback", once=True)
        def cancel_cleanup(_session):
            event.remove(self.db.sync_session, "after_commit", cleanup_after_commit)

    @staticmethod
    async def _delete_objects(config, keys):
        adapter = StorageAdapterFactory.create(config)
        try:
            for key in keys:
                try:
                    await adapter.delete(key)
                except Exception:
                    # shortcut: 清理失败的对象不可再访问；需要自动重试时增加持久化清理队列。
                    logger.exception("档案物理对象清理失败: {}", key)
        finally:
            await adapter.close()

    async def exists(self, source_id, remote_path, bucket=None):
        await self._prepare(source_id, bucket)
        entry = self._entries.get(self._validate_remote_path(remote_path))
        return bool(entry and self._readable(entry))

    async def mkdir(self, source_id, remote_dir, bucket=None, visibility="private"):
        path = self._validate_remote_path(remote_dir)
        await self._prepare(source_id, bucket, lock=True, action="update")
        parent = self._destination(path)
        self._new_entry(path, parent, visibility, True)
        await self.db.flush()
        return StoragePathCreateSchema(path=path)

    async def set_visibility(self, source_id, remote_path, visibility, bucket=None):
        await self._prepare(source_id, bucket, lock=True, action="update")
        entry = self._require(self._validate_remote_path(remote_path), manage=True)
        if entry.parent_id is not None:
            raise CustomException(msg="此条目继承文件夹范围，请修改顶层文件夹的共享范围")
        self._subtree(entry, manage=True)
        self._scope(visibility)
        entry.visibility = visibility
        if visibility == "department":
            entry.dept_id = self._dept_id
        await self.db.flush()

    async def rename(self, source_id, src_path, dst_path, bucket=None):
        src, dst = self._validate_remote_path(src_path), self._validate_remote_path(dst_path)
        await self._prepare(source_id, bucket, lock=True, action="update")
        entry = self._require(src, manage=True)
        entries = self._subtree(entry, manage=True)
        if dst == src or dst.startswith(src + "/"):
            raise CustomException(msg="目标不能是原路径或其子目录")
        parent = self._destination(dst)
        for child in entries:
            new_path = dst + child.path[len(src):]
            if len(new_path) > 500 or new_path in self._entries:
                raise CustomException(msg="目标路径冲突或过长")
        entry.parent_id = parent.id if parent else None
        root = self._root(entry)
        if parent is None:
            entry.visibility, entry.dept_id = root.visibility, root.dept_id
        for child in entries:
            child.path = dst + child.path[len(src):]
        await self.db.flush()
        return StoragePathResultSchema(source_path=src, target_path=dst)

    async def copy_or_move(self, source_id, source_path, target_id, target_path, move=False, bucket=None):
        await self._prepare(source_id, bucket, lock=True, action="update")
        source_id = self._node.id
        if move and source_id == target_id:
            return await self.rename(source_id, source_path, target_path, bucket)
        entry = self._require(self._validate_remote_path(source_path), manage=move)
        if entry.is_dir:
            raise CustomException(msg="暂不支持跨存储源复制或移动目录")
        scope = self._root(entry).visibility
        path, _ = await self.download(source_id, entry.path, bucket)
        try:
            with open(path, "rb") as stream:
                await self.upload(target_id, UploadFile(filename=Path(target_path).name, file=stream), target_path,
                                  bucket=bucket if target_id == source_id else None, visibility=scope)
            if move:
                await self.delete(source_id, source_path, bucket)
        finally:
            os.unlink(path)
        return StoragePathResultSchema(source_path=source_path, target_path=target_path)

    async def list_buckets(self, source_id):
        await self._context()
        node = await self._source(source_id)
        return [node.bucket] if node.bucket else []

    async def share(self, source_id, remote_path, expire=3600, bucket=None):
        raise CustomException(msg="档案文件不提供匿名链接，请通过共享范围授权成员访问")

    async def create_bucket(self, source_id: int | None, bucket: str) -> None:
        """创建存储桶（仅对象存储协议）。

        桶名只做与协议无关的通用校验（非空/长度/非法字符）；各协议的命名细则
        （如 COS 的 ``-appid`` 后缀、S3 的区域约束）交给 SDK 报错。
        """
        name = (bucket or "").strip()
        if not name:
            raise CustomException(msg="桶名不能为空")
        if len(name) > 63:
            raise CustomException(msg="桶名长度不能超过 63 个字符")
        if any(ch in name for ch in ("/", "\\", " ", "\t", "\n")):
            raise CustomException(msg="桶名不能包含空格或斜杠")
        config = await self._get_source(source_id)
        if config.protocol not in _OBJECT_STORE_PROTOCOLS:
            raise CustomException(msg="仅对象存储协议（S3/OSS/COS/OBS）支持创建桶")
        adapter = StorageAdapterFactory.create(config)
        try:
            await adapter.create_bucket(name)
        finally:
            await adapter.close()
