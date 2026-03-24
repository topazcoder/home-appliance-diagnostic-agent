from uuid import UUID
from pydantic import BaseModel, Field


class SessionData(BaseModel):
    id: UUID | None = None
    history: list = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
