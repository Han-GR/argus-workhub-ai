"""企业知识库共用的向量配置，仅管理员维护。"""

import json
import math
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator
from redis.asyncio import Redis

from app.core.exceptions import CustomException
from app.utils.crypto_util import CryptoUtil

ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


class EmbeddingConfigInput(BaseModel):
    base_url: Literal["https://open.bigmodel.cn/api/paas/v4", "https://api.siliconflow.cn/v1"] = ZHIPU_BASE_URL
    model_id: Literal["embedding-3", "BAAI/bge-m3"] = "embedding-3"
    dimensions: Literal[256, 512, 1024, 2048] = 1024
    api_key: str = Field(default="", max_length=500, repr=False)

    @model_validator(mode="after")
    def validate_provider_model(self) -> "EmbeddingConfigInput":
        if self.base_url == SILICONFLOW_BASE_URL:
            if self.model_id != "BAAI/bge-m3" or self.dimensions != 1024:
                raise ValueError("硅基流动使用 BAAI/bge-m3，向量维度固定为 1024")
        elif self.model_id != "embedding-3":
            raise ValueError("智谱使用 embedding-3")
        return self

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if value and (not value.strip() or any(char.isspace() for char in value)):
            raise ValueError("API Key 不能包含空白字符")
        return value


def _config_key() -> str:
    return "ai_knowledge:embedding_config"


async def read_embedding_config(redis: Redis) -> dict[str, Any] | None:
    raw = await redis.get(_config_key())
    if not raw:
        return None
    config = json.loads(raw)
    config["api_key"] = CryptoUtil.decrypt(config["api_key"])
    return config


async def get_embedding_config(redis: Redis) -> dict[str, Any]:
    raw = await redis.get(_config_key())
    config = json.loads(raw) if raw else EmbeddingConfigInput(base_url=SILICONFLOW_BASE_URL, model_id="BAAI/bge-m3").model_dump()
    config.pop("api_key", None)
    return {**config, "configured": bool(raw), "has_api_key": bool(raw)}


async def _resolve_key(redis: Redis, data: EmbeddingConfigInput) -> str:
    if data.api_key:
        return data.api_key
    saved = await read_embedding_config(redis)
    if not saved or saved["base_url"] != data.base_url:
        raise CustomException(msg="请先填写当前服务商的 API Key")
    return saved["api_key"]


async def save_embedding_config(redis: Redis, data: EmbeddingConfigInput) -> dict[str, Any]:
    key = await _resolve_key(redis, data)
    config = {**data.model_dump(), "api_key": CryptoUtil.encrypt(key)}
    # 配置不设置过期时间，避免长期未登录后丢失知识库所用凭据。
    await redis.set(_config_key(), json.dumps(config))
    return await get_embedding_config(redis)


async def test_embedding_config(redis: Redis, data: EmbeddingConfigInput) -> dict[str, Any]:
    key = await _resolve_key(redis, data)
    started = time.perf_counter()
    vectors = await embed_texts({**data.model_dump(), "api_key": key}, ["Argus 知识库连接测试"])
    return {"ok": True, "model_id": data.model_id, "dimensions": len(vectors[0]), "latency_ms": int((time.perf_counter() - started) * 1000)}


async def embed_texts(config: dict[str, Any], texts: list[str]) -> list[list[float]]:
    """测试与知识库共用实际向量调用；批次由调用方限制。"""
    data = EmbeddingConfigInput(**config)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            body: dict[str, Any] = {"model": data.model_id, "input": texts}
            if data.base_url == ZHIPU_BASE_URL:
                body["dimensions"] = data.dimensions
            response = await client.post(
                f"{data.base_url}/embeddings",
                headers={"Authorization": f"Bearer {data.api_key}"},
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise CustomException(msg="向量模型请求超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise CustomException(msg="无法连接向量接口，请检查网络后重试") from exc
    if response.status_code != 200:
        hints = {401: "请检查 API Key", 403: "请检查模型访问权限", 429: "请求限流或额度不足，请检查账户后重试"}
        hint = hints.get(response.status_code, "向量服务暂不可用，请稍后重试")
        raise CustomException(msg=f"向量模型调用失败（HTTP {response.status_code}），{hint}")
    try:
        items = response.json()["data"]
        if len(items) != len(texts):
            raise ValueError("invalid batch")
        # 单条测试兼容无 index 的响应；批量必须校验位置，防止原文与向量错配。
        if len(items) > 1:
            items = sorted(items, key=lambda item: item["index"])
            if [item["index"] for item in items] != list(range(len(texts))):
                raise ValueError("invalid indices")
        vectors = [item["embedding"] for item in items]
        for vector in vectors:
            if not (isinstance(vector, list) and len(vector) == data.dimensions and all(type(v) in (int, float) and math.isfinite(v) for v in vector)):
                raise ValueError("invalid embedding")
    except (ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
        raise CustomException(msg="接口返回的向量格式或维度不正确，请重试") from exc
    return vectors
