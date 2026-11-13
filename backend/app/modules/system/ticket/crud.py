from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import TicketCommentModel, TicketModel
from .schema import TicketCommentCreateSchema, TicketCreateSchema, TicketUpdateSchema


class TicketCRUD(CRUDBase[TicketModel, TicketCreateSchema, TicketUpdateSchema]):
    """任务 CRUD"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=TicketModel, auth=auth, db=db)


    async def _permission_condition(self):
        condition = await super()._permission_condition()
        if condition is None:
            return None
        return or_(condition, TicketModel.assigned_id == self.auth.user.id)


class TicketCommentCRUD(CRUDBase[TicketCommentModel, TicketCommentCreateSchema, Any]):
    """任务评论 CRUD"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=TicketCommentModel, auth=auth, db=db)


    async def _permission_condition(self):
        parent = TicketCRUD(self.auth, self.db)
        conditions = await parent._build_conditions()
        return TicketCommentModel.ticket_id.in_(select(TicketModel.id).where(*conditions))
