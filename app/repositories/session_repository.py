from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SessionModel


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_call_sid(self, call_sid: str) -> SessionModel | None:
        result = await self.db.execute(select(SessionModel).where(SessionModel.call_sid == call_sid))
        return result.scalar_one_or_none()
    
    async def get_latest_by_call_sid(self, call_sid: str) -> SessionModel | None:
        result = await self.db.execute(
            select(SessionModel)
            .where(SessionModel.call_sid == call_sid)
            .order_by(desc(SessionModel.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self,  call_sid: str) -> UUID:
        session = SessionModel(call_sid=call_sid)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session.id

    async def update(self, session: SessionModel, history: list, context: dict) -> SessionModel:
        session.history = history
        session.context = context
        await self.db.commit()
        await self.db.refresh(session)
        return session
