"""AI 只读工具注册与签名守卫。"""

from __future__ import annotations

import pytest

from app.modules.ai.tools import registry as r




def test_injected_param_guard() -> None:
    def bad(auth): ...
    with pytest.raises(RuntimeError, match="闭包参数"):
        r._assert_no_injected_params([r.ReadonlyToolSpec("bad", "x", bad)])








async def test_storage_files_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    class Ctx:
        async def __aenter__(self): return object()
        async def __aexit__(self,*a): return False
    monkeypatch.setattr(r,"async_db_session",lambda: Ctx())
    class N:
        def __init__(self,*a): pass
        async def get_list(self): return [SimpleNamespace(id=1,name="n")]
    monkeypatch.setattr(r,"StorageNodeService",N)
    tools={t.name:t for t in r.build_readonly_tools(object())}
    out=await tools["storage_files"].func("x")
    assert out["error"].startswith("存储源不存在") and out["available"]==["n"]


async def test_storage_tools_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    class Ctx:
        async def __aenter__(self): return object()
        async def __aexit__(self,*a): return False
    monkeypatch.setattr(r,"async_db_session",lambda: Ctx())
    class N:
        def __init__(self,*a): pass
        async def get_list(self): return [SimpleNamespace(id=1,name="n",protocol="s3",status=0,is_default=True)]
    monkeypatch.setattr(r,"StorageNodeService",N)
    class F:
        def __init__(self,*a): pass
        async def list_files(self,**kw): return [SimpleNamespace(name="a",is_dir=False,size=1)]
    monkeypatch.setattr(r,"StorageFileService",F)
    tools={t.name:t for t in r.build_readonly_tools(object())}
    sources=await tools["storage_sources"].func()
    assert sources[0]["name"]=="n"
    files=await tools["storage_files"].func("n")
    assert files["entries"][0]["name"]=="a"
