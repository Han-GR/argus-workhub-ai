"""在线用户服务分支测试（fake Redis/DB）。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.monitor.online.service import OnlineService

pytestmark = pytest.mark.asyncio


async def test_online_list_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.redis_crud import RedisCURD
    sessions = {
        "a": json.dumps({"user_id": 1, "name": "Alice", "ipaddr": "1.1.1.1", "login_location": "Beijing", "login_time": "1"}),
        "b": json.dumps({"user_id": 2, "name": "Bob", "ipaddr": "2.2.2.2", "login_location": "Shanghai", "login_time": "2"}),
    }
    async def scan(_pattern): return [b"access_token:a", b"access_token:b"]
    async def mget(_keys): return [b"tok-a", b"tok-b"]
    async def get(key):
        sid = key.rsplit(":", 1)[-1]
        return sessions.get(sid)
    async def delete(*_keys): pass
    monkeypatch.setattr(RedisCURD, "scan_keys", staticmethod(scan))
    monkeypatch.setattr(RedisCURD, "mget", staticmethod(mget))
    monkeypatch.setattr(RedisCURD, "get", staticmethod(get))
    monkeypatch.setattr(RedisCURD, "delete", staticmethod(delete))
    monkeypatch.setattr("app.modules.monitor.online.service.decode_access_token", lambda token: SimpleNamespace(sub=(token.decode() if isinstance(token, bytes) else token)[-1]))
    online = await OnlineService.get_online_list(object())
    assert [x["name"] for x in online] == ["Bob", "Alice"]
    assert [x["name"] for x in await OnlineService.get_current_user_sessions(object(), 1)] == ["Alice"]


async def test_online_invalid_token_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.redis_crud import RedisCURD
    deleted = []
    async def scan(_): return ["access_token:x"]
    async def mget(_): return ["bad"]
    async def delete(*keys): deleted.extend(keys)
    monkeypatch.setattr(RedisCURD, "scan_keys", staticmethod(scan))
    monkeypatch.setattr(RedisCURD, "mget", staticmethod(mget))
    monkeypatch.setattr(RedisCURD, "delete", staticmethod(delete))
    monkeypatch.setattr("app.modules.monitor.online.service.decode_access_token", lambda token: (_ for _ in ()).throw(ValueError()))
    assert await OnlineService.get_online_list(object()) == []
    assert len(deleted) == 3


async def test_online_missing_session_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.redis_crud import RedisCURD
    async def scan(_): return ["access_token:x"]
    async def mget(_): return ["tok"]
    async def get(_): return None
    async def delete(*_): pass
    monkeypatch.setattr(RedisCURD, "scan_keys", staticmethod(scan))
    monkeypatch.setattr(RedisCURD, "mget", staticmethod(mget))
    monkeypatch.setattr(RedisCURD, "get", staticmethod(get))
    monkeypatch.setattr(RedisCURD, "delete", staticmethod(delete))
    monkeypatch.setattr("app.modules.monitor.online.service.decode_access_token", lambda token: SimpleNamespace(sub="s"))
    assert await OnlineService.get_online_list(object()) == []
