"""登录前用户可用性准备。"""

from __future__ import annotations

from types import SimpleNamespace

import json

import pytest

from app.core.exceptions import CustomException
from app.modules.system.auth.service import LoginService










async def test_write_login_log_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.modules.system.auth.service as mod
    class C:
        def __init__(self,*a): pass
        async def create(self,**k): raise RuntimeError("x")
    monkeypatch.setattr(mod, "LoginLogCRUD", C)
    assert await mod._write_login_log(username="u", status=1, login_ip="1", login_location="x", request_os="o", request_browser="b", msg="m") is None




async def test_captcha_missing_and_bad(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.modules.system.auth.service as mod
    monkeypatch.setattr(mod.settings, "CAPTCHA_ENABLE", True)
    form = SimpleNamespace(captcha_key=None, login_type=1, username="user_1")
    with pytest.raises(CustomException):
        await mod.LoginService.authenticate_user(SimpleNamespace(headers={}, client=None, method="POST", url=SimpleNamespace(path="/")), None, form, None)
    form2 = SimpleNamespace(captcha_key="k", login_type=1, username="user_1")
    class Cap:
        @staticmethod
        async def check_captcha(**k): raise CustomException(msg="bad")
    monkeypatch.setattr(mod, "CaptchaService", Cap)
    from unittest.mock import AsyncMock
    monkeypatch.setattr(mod.LoginService, "_check_login_rate_limit", AsyncMock())
    monkeypatch.setattr(mod.IpLocalUtil, "resolve_location", AsyncMock(return_value="x"))
    with pytest.raises(CustomException):
        await mod.LoginService.authenticate_user(SimpleNamespace(headers={}, client=None, method="POST", url=SimpleNamespace(path="/")), None, form2, None)


def test_login_service_init() -> None:
    from app.modules.system.auth.service import LoginService
    obj = LoginService(object(), object())
    assert obj.auth is not None and obj.db is not None




async def test_refresh_token_edges(monkeypatch) -> None:
    import app.modules.system.auth.service as mod
    payload = SimpleNamespace(is_refresh=True, sub="s")
    monkeypatch.setattr(mod, "decode_access_token", lambda *a, **k: payload)
    class R:
        def __init__(self,*a): pass
        async def get(self, key):
            return json.dumps({"session_id": "s", "user_id": 1}) if "session" in key and "refresh" not in key else b"refresh"
        async def delete(self, *a): pass
    class U:
        def __init__(self,*a): pass
        async def get(self, **k): return None
    monkeypatch.setattr(mod, "RedisCURD", R); monkeypatch.setattr(mod, "UserCRUD", U)
    with pytest.raises(CustomException):
        await mod.LoginService.refresh_token(None, None, "refresh")
    class R2(R):
        async def get(self, key):
            return json.dumps({"session_id": "s"}) if "session" in key and "refresh" not in key else b"refresh"
    monkeypatch.setattr(mod, "RedisCURD", R2)
    with pytest.raises(CustomException):
        await mod.LoginService.refresh_token(None, None, "refresh")




async def test_captcha_states(monkeypatch) -> None:
    import app.modules.system.auth.service as mod
    class Cap(mod.CaptchaService):
        PENDING = 0; VERIFIED = 1
        @staticmethod
        async def _read_state(**k): return {"status": 9, "target_x": 0, "issued_at": 0, "fingerprint": "f"}
    monkeypatch.setattr(mod, "CaptchaService", Cap)
    with pytest.raises(CustomException):
        await mod.CaptchaService.slider_complete(redis=None, request=None, captcha_key="k", position=0)
    class Cap2(Cap):
        @staticmethod
        async def _read_state(**k): return {"status": 0, "target_x": 0, "issued_at": 0, "fingerprint": "f"}
        @staticmethod
        def _matches(state, request): return False
    monkeypatch.setattr(mod, "CaptchaService", Cap2)
    with pytest.raises(CustomException):
        await Cap2.slider_complete(redis=None, request=None, captcha_key="k", position=0)
