import json

from redis.asyncio.client import Redis

from app.common.enums import RedisInitKeyConfig
from app.core.redis_crud import RedisCURD
from app.core.security import decode_access_token



class OnlineService:
    """在线用户管理模块服务层"""

    @staticmethod
    async def get_online_list(redis: Redis) -> list[dict]:
        keys = await RedisCURD(redis).scan_keys(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:*")
        tokens = await RedisCURD(redis).mget(keys)

        online_users = []
        for key, token in zip(keys, tokens, strict=True):
            if not token:
                continue
            try:
                payload = decode_access_token(token=token)
                session_id = payload.sub

                # 从 Redis 读取完整会话信息
                raw = await RedisCURD(redis).get(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")
                if not raw:
                    continue
                session_info = json.loads(raw)

                online_users.append(session_info)
            except Exception:
                # token 已过期或无效，清理 Redis 中的脏数据
                key_str = key.decode() if isinstance(key, bytes) else key
                session_id = key_str.split(":")[-1]
                await RedisCURD(redis).delete(key_str)
                await RedisCURD(redis).delete(f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}")
                await RedisCURD(redis).delete(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")
                continue

        online_users.sort(key=lambda x: x.get("login_time", ""), reverse=True)
        return online_users

    @staticmethod
    async def get_current_user_sessions(redis: Redis, user_id: int) -> list[dict]:
        """获取当前用户的在线会话列表"""
        all_online = await OnlineService.get_online_list(redis)
        return [s for s in all_online if s.get("user_id") == user_id]
