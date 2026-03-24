from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AvailabilitySlotModel, TechnicianModel


class TechnicianRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all(self) -> list[TechnicianModel]:
        result = await self.db.execute(select(TechnicianModel))
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[TechnicianModel]:
        result = await self.db.execute(
            select(TechnicianModel).where(TechnicianModel.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[TechnicianModel]:
        result = await self.db.execute(
            select(TechnicianModel).where(TechnicianModel.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> TechnicianModel:
        technician = TechnicianModel(**fields)
        self.db.add(technician)
        await self.db.commit()
        await self.db.refresh(technician)
        return technician

    async def update(self, technician: TechnicianModel, **fields) -> TechnicianModel:
        for key, value in fields.items():
            setattr(technician, key, value)
        await self.db.commit()
        await self.db.refresh(technician)
        return technician

    async def delete(self, technician: TechnicianModel) -> None:
        await self.db.delete(technician)
        await self.db.commit()

    async def get_available_slots(self, technician_id: UUID) -> list[AvailabilitySlotModel]:
        result = await self.db.execute(
            select(AvailabilitySlotModel).where(
                AvailabilitySlotModel.technician_id == technician_id,
                AvailabilitySlotModel.is_booked     == False,
                AvailabilitySlotModel.slot_datetime  > datetime.now(timezone.utc),
            )
        )
        return result.scalars().all()

    async def get_slot_by_id(self, slot_id: UUID) -> AvailabilitySlotModel | None:
        result = await self.db.execute(
            select(AvailabilitySlotModel).where(
                AvailabilitySlotModel.id == slot_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_slot_booked(self, slot: AvailabilitySlotModel) -> None:
        slot.is_booked = True
        await self.db.commit()
