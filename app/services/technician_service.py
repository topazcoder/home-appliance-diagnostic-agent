from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.service_entities import Technician
from app.repositories.technician_repository import TechnicianRepository


class TechnicianService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = TechnicianRepository(db)

    async def get_all(self) -> list[Technician]:
        technicians = await self.repository.get_all()
        return [Technician.model_validate(t) for t in technicians]

    async def get_by_id(self, id: UUID) -> Optional[Technician]:
        technician = await self.repository.get_by_id(id)
        if technician is None:
            return None
        return Technician.model_validate(technician)

    async def create(self, **fields) -> Technician:
        if fields.get('email'):
            existing = await self.repository.get_by_email(fields['email'])
            if existing:
                raise ValueError(f"Technician with email '{fields['email']}' already exists")
        technician = await self.repository.create(**fields)
        return Technician.model_validate(technician)

    async def update(self, id: UUID, **fields) -> Optional[Technician]:
        technician = await self.repository.get_by_id(id)
        if technician is None:
            return None
        updated = await self.repository.update(technician, **fields)
        return Technician.model_validate(updated)

    async def delete(self, id: UUID) -> bool:
        technician = await self.repository.get_by_id(id)
        if technician is None:
            return False
        await self.repository.delete(technician)
        return True
