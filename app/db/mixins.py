# mypy: disable-error-code="assignment"
from datetime import datetime

from sqlalchemy import TIMESTAMP, Column
from sqlalchemy.orm import Mapped


class TimestampsMixin:
    created_at: Mapped[datetime] = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = Column(TIMESTAMP(timezone=True), nullable=False)
