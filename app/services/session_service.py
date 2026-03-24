from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.session_repository import SessionRepository
from app.entities.service_entities import SessionData


class SessionService:
    def __init__(self, db: AsyncSession):
        self.repository = SessionRepository(db)

    async def create(self, call_sid: str) -> UUID:
        return await self.repository.create(call_sid)

    async def load(self, call_sid: str) -> SessionData:
        session = await self.repository.get_by_call_sid(call_sid)
        if session is None:
            raise ValueError(f"Session with id {id} not found")
        return SessionData(
            id=session.id,
            history=session.history or [],
            context=session.context or {},
        )

    async def load_latest(self, call_sid: str) -> SessionData:
        session = await self.repository.get_latest_by_call_sid(call_sid)
        if session is None:
            raise ValueError(f"Session with id {id} not found")
        return SessionData(
            id=session.id,
            history=session.history or [],
            context=session.context or {},
        )

    async def save(self, call_sid: str, data: SessionData) -> None:
        session = await self.repository.get_by_call_sid(call_sid)
        if session is None:
            raise ValueError(f"Session with call sid {call_sid} not found")

        await self.repository.update(session, data.history, data.context)
