import json
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from app.core.exceptions import CustomException
from app.modules.ai.knowledge import embedding


class MemoryRedis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value


async def test_config_is_encrypted_shared_and_blank_key_preserves_secret():
    redis = MemoryRedis()
    config = embedding.EmbeddingConfigInput(api_key="test-private-key", dimensions=512)
    result = await embedding.save_embedding_config(redis, config)
    assert result["has_api_key"] is True and "api_key" not in result
    assert "test-private-key" not in json.dumps(redis.data)
    assert (await embedding.read_embedding_config(redis))["api_key"] == "test-private-key"
    await embedding.save_embedding_config(redis, embedding.EmbeddingConfigInput(dimensions=1024))
    stored = await embedding.read_embedding_config(redis)
    assert stored["api_key"] == "test-private-key"
    assert stored["dimensions"] == 1024
    assert "api_key" not in await embedding.get_embedding_config(redis)


async def test_siliconflow_probe_and_cross_provider_secret_isolation(monkeypatch):
    redis = MemoryRedis()
    await embedding.save_embedding_config(redis, embedding.EmbeddingConfigInput(api_key="zhipu-secret"))
    config = embedding.EmbeddingConfigInput(base_url=embedding.SILICONFLOW_BASE_URL, model_id="BAAI/bge-m3")
    post = AsyncMock(return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1024}]}))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    for action in (embedding.save_embedding_config, embedding.test_embedding_config):
        with pytest.raises(CustomException, match="当前服务商"):
            await action(redis, config)
    post.assert_not_awaited()
    config.api_key = "siliconflow-secret"
    result = await embedding.test_embedding_config(redis, config)
    assert result["dimensions"] == 1024
    assert post.call_args.args[0] == "https://api.siliconflow.cn/v1/embeddings"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer siliconflow-secret"
    assert post.call_args.kwargs["json"] == {"model": "BAAI/bge-m3", "input": ["Argus 知识库连接测试"]}
    await embedding.save_embedding_config(redis, config)
    assert "siliconflow-secret" not in json.dumps(redis.data)
    config.api_key = ""
    await embedding.test_embedding_config(redis, config)
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer siliconflow-secret"


@pytest.mark.parametrize(
    "values",
    [
        {"base_url": embedding.SILICONFLOW_BASE_URL},
        {"model_id": "BAAI/bge-m3"},
        {"base_url": embedding.SILICONFLOW_BASE_URL, "model_id": "BAAI/bge-m3", "dimensions": 512},
    ],
)
def test_provider_model_dimensions_must_match(values):
    with pytest.raises(ValidationError):
        embedding.EmbeddingConfigInput(**values)


async def test_first_save_requires_key():
    with pytest.raises(CustomException, match="API Key"):
        await embedding.save_embedding_config(MemoryRedis(), embedding.EmbeddingConfigInput())


def test_config_rejects_untrusted_endpoint_and_invalid_dimensions():
    for values in ({"base_url": "http://127.0.0.1"}, {"dimensions": 12}, {"api_key": "\n"}):
        with pytest.raises(ValidationError):
            embedding.EmbeddingConfigInput(**values)


async def test_probe_uses_embedding_endpoint_and_validates_vector(monkeypatch):
    redis = MemoryRedis()
    await embedding.save_embedding_config(redis, embedding.EmbeddingConfigInput(api_key="stored-secret", dimensions=256))
    post = AsyncMock(return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 256}]}))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    result = await embedding.test_embedding_config(redis, embedding.EmbeddingConfigInput(dimensions=256))
    assert result["ok"] and result["dimensions"] == 256
    assert post.call_args.args[0] == embedding.ZHIPU_BASE_URL + "/embeddings"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer stored-secret"
    assert post.call_args.kwargs["json"]["dimensions"] == 256
    assert "stored-secret" not in json.dumps(result)


@pytest.mark.parametrize("payload", [{}, {"data": []}, {"data": [{"embedding": [1]}]}, {"data": [{"embedding": ["bad"] * 256}]}, {"data": [{"embedding": [float("inf")] * 256}]}])
async def test_probe_rejects_malformed_success(monkeypatch, payload):
    class Response:
        status_code = 200

        def json(self):
            return payload

    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=Response()))
    with pytest.raises(CustomException, match="向量"):
        await embedding.test_embedding_config(MemoryRedis(), embedding.EmbeddingConfigInput(api_key="secret", dimensions=256))


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_probe_errors_do_not_disclose_key(monkeypatch, status):
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=httpx.Response(status, text="secret")))
    with pytest.raises(CustomException) as exc:
        await embedding.test_embedding_config(MemoryRedis(), embedding.EmbeddingConfigInput(api_key="secret"))
    assert "secret" not in str(exc.value)
    assert str(status) in str(exc.value)


async def test_probe_timeout_is_actionable(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(side_effect=httpx.ReadTimeout("secret")))
    with pytest.raises(CustomException, match="超时"):
        await embedding.test_embedding_config(MemoryRedis(), embedding.EmbeddingConfigInput(api_key="secret"))
