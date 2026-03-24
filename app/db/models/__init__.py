from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import *


class TechnicianModel(Base):
    """Model for technicians"""

    __tablename__ = 'technicians'
    __table_args__ = ()

    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, index=True, unique=True, nullable=True)
    zip_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated e.g. "10001,10002"
    specialties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated e.g. "washer,dryer,fridge"
    rating: Mapped[Optional[float]] = mapped_column(Float, default=5.0, nullable=True)

    slots: Mapped[list['AvailabilitySlotModel']] = relationship('AvailabilitySlotModel', back_populates='technician')


class AvailabilitySlotModel(Base):
    """Model for technician availability slots"""

    __tablename__ = 'availability_slots'
    __table_args__ = ()

    technician_id: Mapped[UUID] = mapped_column(ForeignKey('technicians.id'), nullable=False)
    slot_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')

    technician: Mapped['TechnicianModel'] = relationship('TechnicianModel', back_populates='slots')


class AppointmentModel(Base):
    """Model for appointments"""

    __tablename__ = 'appointments'
    __table_args__ = ()

    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    call_sid: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    technician_id: Mapped[UUID] = mapped_column(ForeignKey('technicians.id'), nullable=False)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey('availability_slots.id'), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    appliance_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class KnowledgeChunkModel(Base):
    """Model for knowledge chunks"""

    __tablename__ = 'knowledge_chunks'
    __table_args__ = ()

    appliance_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    symptom_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector, nullable=False)


class SessionModel(Base):
    """Model for sessions"""

    __tablename__ = 'sessions'
    __table_args__ = ()

    call_sid: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    history: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
