from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import *


class SessionData(BaseModel):
    id: UUID = Field()
    history: list = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


class Technician(BaseModel):
    id: UUID = Field()
    name: str = Field()
    phone: str | None = Field(default=None)
    email: str | None = Field(default=None)
    zip_codes: str | None = Field(default=None)
    specialties: str | None = Field(default=None)
    rating: float | None = Field(default=5.0)

    model_config = {'from_attributes': True}


class AvailabilitySlot(BaseModel):
    id: UUID = Field()
    technician_id: UUID = Field()
    slot_datetime: datetime = Field()
    is_booked: bool = Field(default=False)

    model_config = {'from_attributes': True}


class Appointment(BaseModel):
    id: UUID = Field()
    session_id: str = Field()
    technician_id: UUID = Field()
    slot_id: UUID = Field()
    customer_name: str | None = Field(default=None)
    customer_phone: str | None = Field(default=None)
    appliance_type: str | None = Field(default=None)
    symptoms: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)

    model_config = {'from_attributes': True}
