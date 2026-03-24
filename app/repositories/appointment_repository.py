from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppointmentModel


class AppointmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all(self) -> list[AppointmentModel]:
        result = await self.db.execute(select(AppointmentModel))
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[AppointmentModel]:
        result = await self.db.execute(
            select(AppointmentModel).where(AppointmentModel.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_session(self, session_id: str) -> list[AppointmentModel]:
        result = await self.db.execute(
            select(AppointmentModel).where(AppointmentModel.session_id == session_id)
        )
        return list(result.scalars().all())

    async def get_by_technician(self, technician_id: UUID) -> list[AppointmentModel]:
        result = await self.db.execute(
            select(AppointmentModel).where(AppointmentModel.technician_id == technician_id)
        )
        return list(result.scalars().all())

    async def get_by_slot_id(self, slot_id: UUID) -> Optional[AppointmentModel]:
        result = await self.db.execute(
            select(AppointmentModel).where(AppointmentModel.slot_id == slot_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> AppointmentModel:
        appointment = AppointmentModel(**fields)
        self.db.add(appointment)
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def update(self, appointment: AppointmentModel, **fields) -> AppointmentModel:
        for key, value in fields.items():
            setattr(appointment, key, value)
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def delete(self, appointment: AppointmentModel) -> None:
        await self.db.delete(appointment)
        await self.db.commit()
