"""监控控制器基础分支（健康检查/服务器信息/SSE）。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.modules.monitor.health import controller as health
from app.modules.monitor.health.schema import ServiceInfoOut




async def test_health_check_ok_and_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    settings = SimpleNamespace(VERSION="3")
    ok = ServiceInfoOut(name="x", version="1", environment="test", db_status=1, redis_status=1)
    async def collect(_): return ok
    monkeypatch.setattr(health.HealthService, "collect", collect)
    resp = await health.health_check(request, settings)
    body = json.loads(resp.body)
    assert "系统健康" in body["msg"]

    bad = ServiceInfoOut(name="x", version="1", environment="test", db_status=0, redis_status=0)
    async def collect2(_): return bad
    monkeypatch.setattr(health.HealthService, "collect", collect2)
    resp2 = await health.health_check(request, settings)
    assert "服务异常" in json.loads(resp2.body)["msg"]


async def test_health_stream_yields(monkeypatch: pytest.MonkeyPatch) -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    async def collect(_): return ServiceInfoOut(name="x", version="1", environment="test", db_status=1, redis_status=1)
    async def no_sleep(_): return None
    monkeypatch.setattr(health.HealthService, "collect", collect)
    monkeypatch.setattr(health.asyncio, "sleep", no_sleep)
    gen = health.health_stream_controller(request)
    event = await anext(gen)
    assert "db_status" in event.raw_data
    event2 = await anext(gen)
    assert "db_status" in event2.raw_data
    await gen.aclose()
