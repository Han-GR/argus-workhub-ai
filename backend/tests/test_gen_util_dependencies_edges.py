"""代码生成类型工具 / 认证依赖边缘。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import CustomException
import app.core.dependencies as D




async def test_authenticate_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(CustomException):
        await D._authenticate("", None, None)
    with pytest.raises(CustomException):
        await D._authenticate("Bearer ", None, None)
    monkeypatch.setattr(D, "decode_access_token", lambda *a, **k: None)
    with pytest.raises(CustomException):
        await D._authenticate("x", None, None)
    payload = SimpleNamespace(is_refresh=True, sub="s")
    monkeypatch.setattr(D, "decode_access_token", lambda *a, **k: payload)
    with pytest.raises(CustomException):
        await D._authenticate("x", None, None)
    payload = SimpleNamespace(is_refresh=False, sub=None)
    monkeypatch.setattr(D, "decode_access_token", lambda *a, **k: payload)
    with pytest.raises(CustomException):
        await D._authenticate("x", None, None)


async def test_authenticate_session_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = SimpleNamespace(is_refresh=False, sub="s")
    monkeypatch.setattr(D, "decode_access_token", lambda *a, **k: payload)
    class R:
        def __init__(self, *a): pass
        async def get(self, *a): return None
    monkeypatch.setattr(D, "RedisCURD", R)
    with pytest.raises(CustomException):
        await D._authenticate("x", None, object())
