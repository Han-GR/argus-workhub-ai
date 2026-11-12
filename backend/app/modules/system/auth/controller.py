from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ErrorResponse, ResponseSchema, SuccessResponse
from app.config.setting import settings
from app.core.base_schema import JWTOutSchema
from app.core.dependencies import db_getter, get_current_user, redis_getter
from app.core.logger import logger
from app.core.router_class import OperationLogRoute
from app.core.security import CustomOAuth2PasswordRequestForm

from .schema import (
    CaptchaOutSchema,
    LoginOutSchema,
    SliderCompleteOutSchema,
    SliderCompleteSchema,
)
from .service import (
    CaptchaService,
    LoginService,
)

AuthRouter = APIRouter(route_class=OperationLogRoute, prefix="/auth", tags=["认证授权"])


@AuthRouter.post("/login", summary="登录", response_model=LoginOutSchema)
async def login_for_access_token_controller(
    request: Request,
    redis: Annotated[Redis, Depends(redis_getter)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    login_form: Annotated[CustomOAuth2PasswordRequestForm, Depends()],
) -> JSONResponse | LoginOutSchema:
    login_result: LoginOutSchema = await LoginService.authenticate_user(request=request, redis=redis, login_form=login_form, db=db)

    logger.info(f"用户{login_form.username}登录成功")

    if settings.DOCS_URL in request.headers.get("referer", ""):
        return login_result
    return SuccessResponse(data=login_result, msg="登录成功")


@AuthRouter.post("/token/refresh", summary="刷新token", response_model=ResponseSchema[JWTOutSchema])
async def get_new_token_controller(
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    payload: Annotated[str, Body(description="刷新token参数")],
) -> JSONResponse:
    new_token: JWTOutSchema = await LoginService.refresh_token(db=db, redis=redis, refresh_token=payload)
    return SuccessResponse(data=new_token, msg="刷新成功")


@AuthRouter.get("/captcha/get", summary="获取验证码", response_model=ResponseSchema[CaptchaOutSchema])
async def get_captcha_for_login_controller(
    request: Request,
    redis: Annotated[Redis, Depends(redis_getter)],
) -> JSONResponse:
    captcha: CaptchaOutSchema = await CaptchaService.get_captcha(redis=redis, request=request)
    return SuccessResponse(data=captcha, msg="获取验证码成功")


@AuthRouter.post("/captcha/slider/complete", summary="滑块验证完成", response_model=ResponseSchema[SliderCompleteOutSchema])
async def slider_complete_controller(
    request: Request,
    redis: Annotated[Redis, Depends(redis_getter)],
    body: Annotated[SliderCompleteSchema, Body(description="滑块验证参数")],
) -> JSONResponse:
    result: dict[str, Any] = await CaptchaService.slider_complete(redis=redis, request=request, captcha_key=body.captcha_key, position=body.position)
    return SuccessResponse(data=result, msg="滑块验证成功")


@AuthRouter.post("/logout", summary="退出登录", response_model=ResponseSchema[None], dependencies=[Depends(get_current_user)])
async def logout_controller(
    redis: Annotated[Redis, Depends(redis_getter)],
    payload: Annotated[str, Body(description="退出登录参数")],
) -> JSONResponse:
    if await LoginService.logout(redis=redis, token=payload):
        logger.info("退出成功")
        return SuccessResponse(msg="退出成功")
    return ErrorResponse(msg="退出失败")
