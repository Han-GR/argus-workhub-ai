from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.dependencies import db_getter, get_current_user
from app.core.exceptions import CustomException
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel


async def require_storage_config_admin(
    auth: Annotated[AuthSchema, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(db_getter)],
):
    user = await db.get(UserModel, auth.user.id)
    if user and not user.is_deleted and user.status == 0:
        if user.is_superuser:
            return
        allowed = await db.scalar(select(MenuModel.id)
            .join(RoleMenusModel, RoleMenusModel.menu_id == MenuModel.id)
            .join(RoleModel, RoleModel.id == RoleMenusModel.role_id)
            .join(UserRolesModel, UserRolesModel.role_id == RoleModel.id)
            .where(UserRolesModel.user_id == user.id, RoleModel.status == 0, RoleModel.is_deleted.is_(False),
                   MenuModel.permission == "module_task:storage:node:manage", MenuModel.status == 0,
                   MenuModel.is_deleted.is_(False)).limit(1))
        if allowed:
            return
    raise CustomException(msg="仅存储配置管理员可管理存储源")
