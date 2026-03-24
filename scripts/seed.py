"""Seed script to populate the database with initial data."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.db.database import AsyncSessionLocal
from app.db.models import AppointmentModel, AvailabilitySlotModel, SessionModel, TechnicianModel


TECHNICIANS = [
    {
        "name": "James Carter",
        "phone": "310-555-0101",
        "email": "james.carter@techpro.com",
        "zip_codes": "90001,90002,90003",
        "specialties": "washer,dryer",
        "rating": 4.8,
    },
    {
        "name": "Maria Gonzalez",
        "phone": "713-555-0202",
        "email": "maria.gonzalez@appliancefix.com",
        "zip_codes": "77001,77002,77003",
        "specialties": "fridge,washer,dryer",
        "rating": 4.9,
    },
    {
        "name": "David Nguyen",
        "phone": "206-555-0303",
        "email": "david.nguyen@repairmaster.com",
        "zip_codes": "98101,98102",
        "specialties": "fridge",
        "rating": 4.7,
    },
    {
        "name": "Sarah Mitchell",
        "phone": "305-555-0404",
        "email": "sarah.mitchell@homecare.com",
        "zip_codes": "33101,33102",
        "specialties": "washer",
        "rating": 4.5,
    },
    {
        "name": "Robert Kim",
        "phone": "312-555-0505",
        "email": "robert.kim@fixitfast.com",
        "zip_codes": "60601,60602,60603",
        "specialties": "dryer,fridge",
        "rating": 4.6,
    },
    {
        "name": "Emily Thompson",
        "phone": "212-555-0606",
        "email": "emily.thompson@appliancegeek.com",
        "zip_codes": "10001,10002,10003",
        "specialties": "washer,dryer,fridge",
        "rating": 5.0,
    },
    {
        "name": "Carlos Rivera",
        "phone": "602-555-0707",
        "email": "carlos.rivera@quickfix.com",
        "zip_codes": "85001,85002",
        "specialties": "washer",
        "rating": 4.3,
    },
    {
        "name": "Linda Patel",
        "phone": "404-555-0808",
        "email": "linda.patel@reliablerepair.com",
        "zip_codes": "30301,30302,30303",
        "specialties": "fridge,dryer",
        "rating": 4.7,
    },
    {
        "name": "Michael Johnson",
        "phone": None,
        "email": "michael.johnson@protech.com",
        "zip_codes": "43004",
        "specialties": None,
        "rating": 5.0,
    },
    {
        "name": "Aisha Williams",
        "phone": "704-555-0909",
        "email": "aisha.williams@smartfix.com",
        "zip_codes": "28201,28202",
        "specialties": "washer,fridge",
        "rating": 4.9,
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Clear in dependency order
        await session.execute(delete(SessionModel))
        await session.execute(delete(AppointmentModel))
        await session.execute(delete(AvailabilitySlotModel))
        await session.execute(delete(TechnicianModel))
        await session.commit()
        print("🗑️  Cleared existing data.")

        # Seed technicians
        technician_models: list[TechnicianModel] = []
        for data in TECHNICIANS:
            technician = TechnicianModel(**data)
            session.add(technician)
            technician_models.append(technician)

        await session.commit()
        for t in technician_models:
            await session.refresh(t)
        print(f"✅ Seeded {len(technician_models)} technicians.")

        # Seed availability slots (3 upcoming slots per technician)
        now = datetime.now(timezone.utc)
        slot_models: list[AvailabilitySlotModel] = []
        for technician in technician_models:
            for day_offset in [1, 3, 5]:
                slot = AvailabilitySlotModel(
                    technician_id=technician.id,
                    slot_datetime=now + timedelta(days=day_offset, hours=9),
                    is_booked=False,
                )
                session.add(slot)
                slot_models.append(slot)

        await session.commit()
        for s in slot_models:
            await session.refresh(s)
        print(f"✅ Seeded {len(slot_models)} availability slots.")


if __name__ == "__main__":
    asyncio.run(seed())
