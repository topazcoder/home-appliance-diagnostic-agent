from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    text: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
