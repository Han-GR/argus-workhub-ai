"""模板安全/存储基类边缘。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.task.storage.core.base import BaseStorageAdapter




def test_storage_delete_dir_edges() -> None:
    class A(BaseStorageAdapter):
        def _sync_list_recursive(self, p):
            return [SimpleNamespace(is_dir=True, key="d/sub"), SimpleNamespace(is_dir=False, key="d/a")]
        def _sync_rmdir(self, p): raise RuntimeError("x")
        def _sync_delete(self, p): pass
        def _sync_upload(self, *a): pass
        def _sync_download(self, *a): pass
        def _sync_copy(self, *a): pass
        def _sync_exists(self, *a): return False
        def _sync_list(self, *a): return []
        def _sync_mkdir(self, *a): pass
        def _sync_rename(self, *a): pass
        def _sync_test_connection(self): return True
    a = object.__new__(A)
    a._sync_delete_dir("d")
    assert a._sync_delete_dir("d") is None
