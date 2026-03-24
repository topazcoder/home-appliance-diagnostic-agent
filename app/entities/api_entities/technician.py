from uuid import UUID
from typing import Optional

from pydantic import BaseModel, EmailStr


class TechnicianCreateRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    zip_codes: Optional[str] = None
    specialties: Optional[str] = None
    rating: Optional[float] = 5.0


class TechnicianUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    zip_codes: Optional[str] = None
    specialties: Optional[str] = None
    rating: Optional[float] = None


class TechnicianResponse(BaseModel):
    id: UUID
    name: str
    phone: Optional[str]
    email: Optional[str]
    zip_codes: Optional[str]
    specialties: Optional[str]
    rating: Optional[float]

    model_config = {'from_attributes': True}
