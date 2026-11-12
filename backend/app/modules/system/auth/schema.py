from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schema import JWTOutSchema


class CaptchaOutSchema(BaseModel):
    """验证码响应模型"""

    model_config = ConfigDict(from_attributes=True)

    enable: bool = Field(default=True, description="是否启用验证码")
    key: str = Field(default="", description="验证码唯一标识（未启用验证码时为空字符串）")
    img_base: str = Field(default="", description="拼图背景图（data URI）")
    piece_base: str = Field(default="", description="拼图图块（data URI，透明底）")
    piece_y: int = Field(default=0, description="图块在背景中的 Y 偏移")
    piece_width: int = Field(default=0, description="图块宽度（含凸起）")
    piece_height: int = Field(default=0, description="图块高度")
    bg_width: int = Field(default=320, description="背景宽度")
    bg_height: int = Field(default=160, description="背景高度")


class LoginOutSchema(JWTOutSchema):
    """登录响应"""

    user_info: dict[str, Any] = Field(default_factory=dict, description="用户信息")


class SliderCompleteSchema(BaseModel):
    """滑块验证完成请求"""

    captcha_key: str = Field(..., min_length=1, description="验证码唯一标识")
    position: int | None = Field(default=None, description="拼图图块左侧在背景中的像素位置")


class SliderCompleteOutSchema(BaseModel):
    """滑块验证完成响应"""

    captcha_key: str = Field(..., description="验证码唯一标识")
    verified: bool = Field(default=True, description="是否验证通过")


# =================================================== #
# *************** 微信小程序登录 Schema *************** #
# =================================================== #
