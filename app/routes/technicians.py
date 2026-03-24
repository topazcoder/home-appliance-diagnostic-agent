from uuid import UUID

import structlog

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.entities.api_entities.technician import (
    TechnicianCreateRequest,
    TechnicianUpdateRequest,
    TechnicianResponse,
)
from app.services.technician_service import TechnicianService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix='/api/v1/technicians',
    tags=['technicians'],
    responses={
        200: {'description': 'Success'},
        404: {'description': 'Not found'},
    },
)


@router.get('', response_model=list[TechnicianResponse])
async def get_technicians(
    db: AsyncSession = Depends(get_db),
) -> list[TechnicianResponse]:
    technicians = await TechnicianService(db).get_all()
    return [TechnicianResponse.model_validate(t) for t in technicians]


@router.get('/{technician_id}', response_model=TechnicianResponse)
async def get_technician(
    technician_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TechnicianResponse:
    technician = await TechnicianService(db).get_by_id(technician_id)
    if technician is None:
        raise HTTPException(status_code=404, detail='Technician not found')
    return TechnicianResponse.model_validate(technician)


@router.post('', response_model=TechnicianResponse, status_code=201)
async def create_technician(
    request: TechnicianCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TechnicianResponse:
    try:
        technician = await TechnicianService(db).create(**request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TechnicianResponse.model_validate(technician)


@router.patch('/{technician_id}', response_model=TechnicianResponse)
async def update_technician(
    technician_id: UUID,
    request: TechnicianUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TechnicianResponse:
    fields = request.model_dump(exclude_none=True)
    technician = await TechnicianService(db).update(technician_id, **fields)
    if technician is None:
        raise HTTPException(status_code=404, detail='Technician not found')
    return TechnicianResponse.model_validate(technician)


@router.delete('/{technician_id}', status_code=204)
async def delete_technician(
    technician_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await TechnicianService(db).delete(technician_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Technician not found')
