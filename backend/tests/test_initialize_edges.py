"""初始化迁移/种子数据错误分支。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.scripts.initialize as I


class Conn:
    def __init__(self, has): self.has = has
    async def run_sync(self, fn): return self.has
    async def execute(self, *a, **k): return SimpleNamespace()
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class Engine:
    def __init__(self, has): self.has = has
    def connect(self): return Conn(self.has)






async def test_init_data_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.system.menu.model import MenuModel as M
    class DB:
        async def execute(self, *a, **k): return SimpleNamespace(scalar=lambda: 0)
    obj = object.__new__(I.InitializeData)
    obj.prepare_init_models = [M]
    monkeypatch.setattr(I.InitializeData, "_InitializeData__load_json", staticmethod(lambda n: [{"bad": 1}]))
    with pytest.raises(Exception):
        await obj._InitializeData__init_data(DB())


def test_load_json_errors(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(I, "SCRIPT_DIR", tmp_path)
    (tmp_path / "bad.json").write_text("{bad")
    with pytest.raises(Exception):
        I.InitializeData._InitializeData__load_json("bad")
    (tmp_path / "x.json").write_text("[1]")
    assert I.InitializeData._InitializeData__load_json("x") == [1]




def test_load_json_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(I, "SCRIPT_DIR", tmp_path)
    (tmp_path / "d.json").mkdir()
    with pytest.raises(Exception):
        I.InitializeData._InitializeData__load_json("d")


async def test_init_dict_data_empty(monkeypatch) -> None:
    from app.modules.system.dict.model import DictDataModel
    class DB:
        async def execute(self, *a, **k): return SimpleNamespace(scalar=lambda: 0)
        async def flush(self): pass
    obj = object.__new__(I.InitializeData)
    obj.prepare_init_models = [DictDataModel]
    monkeypatch.setattr(I.InitializeData, "_InitializeData__load_json", staticmethod(lambda n: [{"x": 1}]))
    monkeypatch.setattr(I.InitializeData, "_InitializeData__create_dict_data_objs", AsyncMock(return_value=[]))
    await obj._InitializeData__init_data(DB())
