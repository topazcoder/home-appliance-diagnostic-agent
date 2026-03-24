import uuid

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, TypeDecorator, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.mixins import TimestampsMixin
from app.entities.service_entities import ValidationResults, ValidationRules


class Base(DeclarativeBase, TimestampsMixin):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JSONBValidationRules(TypeDecorator):
    impl = JSONB

    def process_bind_param(self, value, dialect):   # type: ignore[no-untyped-def]
        if value is not None:
            return value.model_dump()
        return value
    
    def process_result_value(self, value, dialect): # type: ignore[no-untyped-def]
        if value is not None:
            return ValidationRules.model_validate(value)
        return value


class JSONBValidationResults(TypeDecorator):
    impl = JSONB

    def process_bind_param(self, value, dialect):   # type: ignore[no-untyped-def]
        if value is not None:
            return value.model_validate(value)
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return ValidationResults.model_validate(value)
        return value
