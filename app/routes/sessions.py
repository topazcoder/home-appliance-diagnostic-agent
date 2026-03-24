import structlog

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat import run_agent
from app.db.database import get_db
from app.entities.api_entities import ChatRequest, ChatResponse
from app.services import SessionService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix='/api/v1/sessions',
    tags=['sessions'],
    responses={
        200: {'description': 'Success'},
        404: {'description': 'Not found'},
    },
)


@router.post('', response_model=str)
async def start_session(
    db: AsyncSession = Depends(get_db),
) -> str:
    session_service = SessionService(db)
    session_id = await session_service.create()

    return str(session_id)


@router.put('', response_model=ChatResponse)
async def update_session(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    session_service = SessionService(db)
    session_data = await session_service.load(request.session_id)
    reply = await run_agent(request.session_id, request.text, session_data, db)
    await session_service.save(request.session_id, session_data)

    return ChatResponse(session_id=request.session_id, reply=reply)
