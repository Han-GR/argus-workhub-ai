import asyncio
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Security, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter, redis_getter
from app.core.exceptions import CustomException

from .embedding import EmbeddingConfigInput, get_embedding_config, save_embedding_config, test_embedding_config
from .service import MAX_FILE_BYTES, KnowledgeService

# 文档、问题和引用含私有资料，不写入通用操作日志的请求/响应正文。
KnowledgeRouter = APIRouter(prefix="/knowledge", tags=["知识库"])
ReadAuth = Annotated[AuthSchema, Security(AuthPermission(["module_ai:knowledge:query"]))]
# 在发送成功响应、执行后台向量清理之前完成文档事务。
DB = Annotated[AsyncSession, Depends(db_getter, scope="function")]
Cache = Annotated[Redis, Depends(redis_getter)]


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class BaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    dept_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("请输入知识库名称")
        return value.strip()


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


@KnowledgeRouter.get("/bases", summary="列出可访问的企业知识库")
async def list_bases(auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).catalog(), msg="")


@KnowledgeRouter.post("/bases", summary="创建企业知识库")
async def create_base(data: BaseInput, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).create_base(data.name, data.dept_id), msg="知识库已创建")


@KnowledgeRouter.delete("/bases/{base_id}", summary="删除空知识库")
async def delete_base(base_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    await KnowledgeService(auth, db, redis, background_tasks).delete_base(str(base_id))
    return SuccessResponse(msg="知识库已删除")


@KnowledgeRouter.get("/bases/{base_id}/documents", summary="列出知识库文档")
async def list_documents(base_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).list_documents(str(base_id)), msg="")


@KnowledgeRouter.post("/bases/{base_id}/documents", summary="上传并索引知识库文档")
async def upload_document(base_id: UUID, auth: ReadAuth, db: DB, redis: Cache, file: UploadFile, background_tasks: BackgroundTasks):
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        name = Path((file.filename or "document").replace("\\", "/")).name[:200]
        async with asyncio.timeout(180):
            result = await KnowledgeService(auth, db, redis, background_tasks).upload(str(base_id), name, content)
        return SuccessResponse(data=result, msg="文档已加入知识库")
    except TimeoutError as exc:
        raise CustomException(msg="文档处理超时，请稍后刷新文档列表确认结果") from exc
    finally:
        await file.close()


@KnowledgeRouter.post("/bases/{base_id}/documents/{doc_id}/reindex", summary="重建文档索引")
async def reindex_document(base_id: UUID, doc_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    try:
        async with asyncio.timeout(180):
            result = await KnowledgeService(auth, db, redis, background_tasks).reindex(str(base_id), str(doc_id))
        return SuccessResponse(data=result, msg="索引已重建")
    except TimeoutError as exc:
        raise CustomException(msg="重建索引超时，请稍后刷新文档列表确认结果") from exc


@KnowledgeRouter.delete("/bases/{base_id}/documents/{doc_id}", summary="删除知识库文档")
async def delete_document(base_id: UUID, doc_id: UUID, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    await KnowledgeService(auth, db, redis, background_tasks).delete(str(base_id), str(doc_id))
    return SuccessResponse(msg="文档已删除")


@KnowledgeRouter.post("/bases/{base_id}/ask", summary="基于知识库问答")
async def ask_knowledge(base_id: UUID, data: QuestionInput, auth: ReadAuth, db: DB, redis: Cache, background_tasks: BackgroundTasks):
    return SuccessResponse(data=await KnowledgeService(auth, db, redis, background_tasks).ask(str(base_id), data.question.strip()), msg="")
