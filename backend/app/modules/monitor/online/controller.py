from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from redis.asyncio.client import Redis

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import get_current_user, redis_getter
from app.core.router_class import OperationLogRoute

from .schema import OnlineOutSchema
from .service import OnlineService

OnlineRouter = APIRouter(route_class=OperationLogRoute, prefix="/online", tags=["在线用户"])


@OnlineRouter.get("/current", summary="获取当前用户的在线会话", response_model=ResponseSchema[list[OnlineOutSchema]], dependencies=[Depends(get_current_user)])
async def get_current_online_controller(
    redis: Annotated[Redis, Depends(redis_getter)],
    auth: Annotated[AuthSchema, Security(get_current_user)],
) -> JSONResponse:
    sessions: list[dict[str, Any]] = await OnlineService.get_current_user_sessions(redis=redis, user_id=auth.user.id)
    return SuccessResponse(data=sessions, msg="获取当前用户在线会话成功")
