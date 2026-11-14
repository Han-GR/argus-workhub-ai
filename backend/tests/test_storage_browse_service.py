"""档案服务边界校验；授权和实际 IO 在 test_archive_permissions 中覆盖。"""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.exceptions import CustomException
from app.modules.task.storage.browse.service import StorageFileService


def test_validate_remote_path():
    assert StorageFileService._validate_remote_path('/a//b/.') == 'a/b'
    for path in ('', '../x', 'a/../b', 'a\x00b', '.', 'a' * 501):
        with pytest.raises(CustomException):
            StorageFileService._validate_remote_path(path)


@pytest.mark.parametrize('name', ['a.exe', 'a', '../a.txt'])
async def test_upload_rejects_invalid_files_before_storage_access(name):
    service = StorageFileService.__new__(StorageFileService)
    with pytest.raises(CustomException):
        await service.upload(None, UploadFile(filename=name, file=BytesIO(b'x')))


async def test_upload_requires_file():
    with pytest.raises(CustomException, match='请选择'):
        await StorageFileService.__new__(StorageFileService).upload(None, None)


def test_zip_directory(tmp_path: Path):
    root = tmp_path / 'root'
    (root / 'sub').mkdir(parents=True)
    (root / 'sub' / 'a.txt').write_text('a')
    zip_path = tmp_path / 'out.zip'
    StorageFileService._zip_directory(root, str(zip_path), root)
    import zipfile
    with zipfile.ZipFile(zip_path) as result:
        assert result.read('sub/a.txt') == b'a'


async def test_anonymous_share_is_disabled():
    with pytest.raises(CustomException, match='不提供匿名链接'):
        await StorageFileService.__new__(StorageFileService).share(1, 'a.txt')
