import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ArchiveSafeStaticFiles
from app.core.exceptions import CustomException
from app.modules.task.storage.core.base import StorageAdapterConfig, StorageProtocol
from app.modules.task.storage.core.local_adapter import LocalStorageAdapter
from app.modules.task.storage.transfer.schema import validate_raw_transfer_path


def test_static_server_never_serves_archive_blobs(tmp_path):
    blob = tmp_path / "upload" / "_argus_archive" / "secret.txt"
    blob.parent.mkdir(parents=True)
    blob.write_text("secret")
    (tmp_path / "public.txt").write_text("public")
    (tmp_path / "alias").symlink_to(blob.parent, target_is_directory=True)
    app = FastAPI()
    app.mount("/static", ArchiveSafeStaticFiles(directory=tmp_path))
    with TestClient(app) as client:
        assert client.get("/static/public.txt").text == "public"
        for path in ("/static/upload/_argus_archive/secret.txt", "/static/upload/%5Fargus_archive/secret.txt", "/static/alias/secret.txt"):
            assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/", ".", "a/../_argus_archive/x", "_argus_archive/x", "a/_argus_archive/x", "_ARGUS_ARCHIVE/x"])
def test_raw_transfer_cannot_read_archive_objects_or_entire_root(path):
    with pytest.raises(ValueError):
        validate_raw_transfer_path(path)


async def test_local_symlinks_cannot_bypass_the_reserved_namespace(tmp_path):
    root = tmp_path / "root"
    protected = root / "_argus_archive"
    protected.mkdir(parents=True)
    (protected / "secret.txt").write_text("secret")
    (root / "alias").symlink_to(protected, target_is_directory=True)
    adapter = LocalStorageAdapter(StorageAdapterConfig(protocol=StorageProtocol.LOCAL, host=str(root), port=0))
    with pytest.raises(CustomException, match="符号链接"):
        await adapter.download("alias/secret.txt", str(tmp_path / "leak.txt"))


def test_local_transfer_cannot_reference_a_server_file():
    from app.modules.task.storage.transfer.schema import TransferTaskCreateSchema
    with pytest.raises(ValueError, match="不能指定服务器文件"):
        TransferTaskCreateSchema(name="bad", task_type="parallel", source_type="local",
            source_path="/etc/passwd", targets=[{"target_id": 1, "target_path": "leak.txt"}])


async def test_json_transfer_endpoint_cannot_create_local_source_tasks():
    from app.modules.task.storage.transfer.schema import TransferTaskCreateSchema
    from app.modules.task.storage.transfer.service import StorageTransferService
    service = StorageTransferService.__new__(StorageTransferService)
    data = TransferTaskCreateSchema(name="bad", task_type="parallel", source_type="local",
        targets=[{"target_id": 1, "target_path": "leak.txt"}])
    with pytest.raises(CustomException, match="文件上传接口"):
        await service.create(data)


async def test_common_file_endpoints_cannot_access_archive_objects(tmp_path, monkeypatch):
    from app.config.setting import settings
    from app.modules.common.file.service import FileService
    from app.utils.upload_util import UploadUtil
    monkeypatch.setattr(settings, "UPLOAD_FILE_PATH", tmp_path)
    blob = tmp_path / "_argus_archive" / "secret.txt"
    blob.parent.mkdir()
    blob.write_text("secret")
    with pytest.raises(CustomException, match="文件管理下载"):
        await FileService.download_service(str(blob))
    with pytest.raises(CustomException, match="档案保留目录"):
        UploadUtil._sanitize_target_path("resource/_ARGUS_ARCHIVE")
