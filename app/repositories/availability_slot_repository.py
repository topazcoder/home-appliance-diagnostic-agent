from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AvailabilitySlotModel


class AvailabilitySlotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all(self) -> list[AvailabilitySlotModel]:
        result = await self.db.execute(select(AvailabilitySlotModel))
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[AvailabilitySlotModel]:
        result = await self.db.execute(
            select(AvailabilitySlotModel).where(AvailabilitySlotModel.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_technician(self, technician_id: UUID) -> list[AvailabilitySlotModel]:
        result = await self.db.execute(
            select(AvailabilitySlotModel).where(AvailabilitySlotModel.technician_id == technician_id)
        )
        return list(result.scalars().all())

    async def get_available_by_technician(self, technician_id: UUID) -> list[AvailabilitySlotModel]:
        result = await self.db.execute(
            select(AvailabilitySlotModel).where(
                AvailabilitySlotModel.technician_id == technician_id,
                AvailabilitySlotModel.is_booked == False,
            )
        )
        return list(result.scalars().all())

    async def create(self, **fields) -> AvailabilitySlotModel:
        slot = AvailabilitySlotModel(**fields)
        self.db.add(slot)
        await self.db.commit()
        await self.db.refresh(slot)
        return slot

    async def update(self, slot: AvailabilitySlotModel, **fields) -> AvailabilitySlotModel:
        for key, value in fields.items():
            setattr(slot, key, value)
        await self.db.commit()
        await self.db.refresh(slot)
        return slot

    async def delete(self, slot: AvailabilitySlotModel) -> None:
        await self.db.delete(slot)
        await self.db.commit()
