from typing import List
from fastapi import APIRouter, Depends, status, Response, Query
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.schemas.event import EventCreate, EventResponse
from src.services.event_service import EventService

router = APIRouter()


@router.post(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Customer Event",
)
def ingest_event(
    dto: EventCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Ingests customer behavioral activity (VIEW_PRODUCT, ADD_TO_CART, PURCHASE).
    Enforces strict idempotency via client-supplied event_key:
    - New event: 201 Created
    - Idempotent retry with identical payload: 200 OK
    - Idempotent key reused with conflicting payload: 409 Conflict
    """
    service = EventService(db)
    event, is_new = service.ingest_event(dto)
    if not is_new:
        response.status_code = status.HTTP_200_OK
    return event


@router.get(
    "/customers/{customer_id}/events",
    response_model=List[EventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Customer Activity History",
)
def get_customer_events(
    customer_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated behavioral interactions for a specific customer in reverse chronological order."""
    service = EventService(db)
    return service.get_customer_history(customer_id, limit=limit, offset=offset)
