import asyncio
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter, get_current_user, redis_getter
from app.core.exceptions import CustomException
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserRolesModel

from .embedding import EmbeddingConfigInput, get_embedding_config, save_embedding_config, test_embedding_config
from .service import MAX_FILE_BYTES, KnowledgeService

# 文档、问题和引用含私有资料，不写入通用操作日志的请求/响应正文。
KnowledgeRouter = APIRouter(prefix="/knowledge", tags=["知识库"])
# 在发送成功响应、执行后台向量清理之前完成文档事务。
DB = Annotated[AsyncSession, Depends(db_getter, scope="function")]
Cache = Annotated[Redis, Depends(redis_getter)]


async def get_knowledge_auth(auth: Annotated[AuthSchema, Depends(get_current_user)], db: DB) -> AuthSchema:
    if auth.user.is_superuser:
        return auth
    # 知识库授权实时查库，撤回入口权限后旧登录会话也必须立即失效。
    permissions = list((await db.scalars(select(MenuModel.permission).distinct()
        .join(RoleMenusModel, RoleMenusModel.menu_id == MenuModel.id)
        .join(RoleModel, RoleModel.id == RoleMenusModel.role_id)
        .join(UserRolesModel, UserRolesModel.role_id == RoleModel.id)
        .where(UserRolesModel.user_id == auth.user.id, RoleModel.status == 0, RoleModel.is_deleted.is_(False),
               MenuModel.status == 0, MenuModel.is_deleted.is_(False), MenuModel.permission.is_not(None)))).all())
    return await AuthPermission(["module_ai:knowledge:query"])(auth.model_copy(update={"permissions": permissions}))


ReadAuth = Annotated[AuthSchema, Depends(get_knowledge_auth)]


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000, pattern=r"\S")


def require_config_admin(auth: ReadAuth) -> AuthSchema:
    if not auth.user.is_superuser:
        raise CustomException(msg="仅超级管理员可配置企业向量模型", code=403)
    return auth


ConfigAuth = Annotated[AuthSchema, Depends(require_config_admin)]


@KnowledgeRouter.get("/embedding", summary="获取企业向量模型配置")
async def embedding_config(auth: ConfigAuth, redis: Cache):
    return SuccessResponse(data=await get_embedding_config(redis), msg="")


@KnowledgeRouter.put("/embedding", summary="保存企业向量模型配置")
async def save_embedding(data: EmbeddingConfigInput, auth: ConfigAuth, redis: Cache):
    return SuccessResponse(data=await save_embedding_config(redis, data), msg="企业向量模型配置已保存")


@KnowledgeRouter.post("/embedding/test", summary="测试企业向量模型（不保存）")
async def test_embedding(data: EmbeddingConfigInput, auth: ConfigAuth, redis: Cache):
    return SuccessResponse(data=await test_embedding_config(redis, data), msg="")


@KnowledgeRouter.get("/workspace", summary="知识库工作区信息")
async def workspace(auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).workspace(), msg="")


@KnowledgeRouter.get("/documents", summary="按权限列出文档")
async def list_documents(auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks,
                         view: Annotated[Literal["all", "company", "department", "mine"], Query()] = "all"):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).list_documents(view), msg="")


@KnowledgeRouter.post("/documents", summary="上传共享文档")
async def upload_document(auth: ReadAuth, db: DB, redis: Cache, file: UploadFile, background_tasks: BackgroundTasks,
                          visibility: Annotated[Literal["company", "department"], Form()]):
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        name = Path((file.filename or "document").replace("\\", "/")).name[:200]
        async with asyncio.timeout(180):
            result = await KnowledgeService(auth, db, redis, background_tasks).upload(name, content, visibility)
        return SuccessResponse(data=result, msg="文档已上传")
    except TimeoutError as exc:
        raise CustomException(msg="文档处理超时，请刷新列表确认结果") from exc
    finally:
        await file.close()


@KnowledgeRouter.put("/documents/{doc_id}", summary="编辑自己上传的文档")
async def update_document(doc_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks,
    name: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    visibility: Annotated[Literal["company", "department"], Form()], file: UploadFile | None = None):
    try:
        content = await file.read(MAX_FILE_BYTES + 1) if file else None
        file_name = Path((file.filename or "document").replace("\\", "/")).name if file else None
        async with asyncio.timeout(180):
            result = await KnowledgeService(auth, db, redis, background_tasks).update(str(doc_id), name.strip(), visibility, file_name, content)
        return SuccessResponse(data=result, msg="文档已更新")
    except TimeoutError as exc:
        raise CustomException(msg="文档更新超时，请刷新列表确认结果") from exc
    finally:
        if file:
            await file.close()


@KnowledgeRouter.post("/documents/{doc_id}/reindex", summary="重建自己上传的文档索引")
async def reindex_document(doc_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    try:
        async with asyncio.timeout(180):
            result = await KnowledgeService(auth, db, redis, background_tasks).reindex(str(doc_id))
        return SuccessResponse(data=result, msg="索引已重建")
    except TimeoutError as exc:
        raise CustomException(msg="重建索引超时，请刷新列表确认结果") from exc


@KnowledgeRouter.delete("/documents/{doc_id}", summary="删除自己上传的文档")
async def delete_document(doc_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    await KnowledgeService(auth, db, redis, background_tasks).delete(str(doc_id))
    return SuccessResponse(msg="文档已删除")


@KnowledgeRouter.post("/ask", summary="基于当前用户可见资料问答")
async def ask_knowledge(data: QuestionInput, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).ask(data.question.strip()), msg="")
