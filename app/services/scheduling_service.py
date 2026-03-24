from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.technician_repository import TechnicianRepository
from app.repositories.appointment_repository import AppointmentRepository


class SchedulingService:

    def __init__(self, db: AsyncSession):
        self.tech_repo        = TechnicianRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    async def find_available_technicians(
        self, zip_code: str, appliance_type: str
    ) -> dict:
        technicians = await self.tech_repo.get_all()
        matches     = []

        for tech in technicians:
            if not tech.zip_codes or not tech.specialties:
                continue
            tech_zips        = [z.strip() for z in tech.zip_codes.split(",")]
            tech_specialties = [s.strip().lower() for s in tech.specialties.split(",")]

            if zip_code in tech_zips and appliance_type.lower() in tech_specialties:
                slots = await self.tech_repo.get_available_slots(tech.id)
                if slots:
                    matches.append({
                        "technician_id":   str(tech.id),
                        "name":            tech.name,
                        "rating":          tech.rating,
                        "available_slots": [
                            {
                                "slot_id":  str(s.id),
                                "datetime": s.slot_datetime.strftime("%A %B %d at %I:%M %p"),
                            }
                            for s in slots[:3]
                        ],
                    })

        if not matches:
            return {
                "found":   False,
                "message": f"No technicians available in {zip_code} for {appliance_type}.",
            }

        return {"found": True, "technicians": matches}

    async def book_appointment(
        self,
        session_id: str,
        call_sid: str,
        slot_id: str,
        technician_id: str,
        customer_name: str,
        customer_phone: str,
        appliance_type: str,
        symptoms: str,
    ) -> dict:
        try:
            slot_uuid = UUID(slot_id)
            tech_uuid = UUID(technician_id)
        except ValueError:
            return {"success": False, "message": "Invalid slot_id or technician_id. Please use the exact IDs returned by find_available_technicians."}

        slot = await self.tech_repo.get_slot_by_id(slot_uuid)
        if not slot:
            return {"success": False, "message": "Slot is no longer available."}

        if slot.is_booked:
            existing = await self.appointment_repo.get_by_slot_id(slot_uuid)
            if existing is not None and existing.call_sid == call_sid:
                tech = await self.tech_repo.get_by_id(tech_uuid)
                return {
                    "success":              True,
                    "appointment_id":       str(existing.id),
                    "technician_name":      tech.name,
                    "slot_datetime":        slot.slot_datetime.strftime("%A %B %d at %I:%M %p"),
                    "confirmation_message": (
                        f"You already have this appointment booked! {tech.name} will visit on "
                        f"{slot.slot_datetime.strftime('%A %B %d at %I:%M %p')}."
                    ),
                }
            return {"success": False, "message": "This slot has already been booked by another caller. Please choose a different slot."}

        await self.tech_repo.mark_slot_booked(slot)

        appointment = await self.appointment_repo.create(
            session_id=session_id,
            call_sid=call_sid,
            technician_id=tech_uuid,
            slot_id=slot_uuid,
            customer_name=customer_name,
            customer_phone=customer_phone,
            appliance_type=appliance_type,
            symptoms=symptoms,
        )

        tech = await self.tech_repo.get_by_id(tech_uuid)

        return {
            "success":              True,
            "appointment_id":       str(appointment.id),
            "technician_name":      tech.name,
            "slot_datetime":        slot.slot_datetime.strftime("%A %B %d at %I:%M %p"),
            "confirmation_message": (
                f"Appointment confirmed! {tech.name} will visit on "
                f"{slot.slot_datetime.strftime('%A %B %d at %I:%M %p')}."
            ),
        }
