from decimal import Decimal
from typing import Tuple, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.repositories.event_repository import EventRepository
from src.repositories.customer_repository import CustomerRepository
from src.models.event import Event
from src.schemas.event import EventCreate
from src.core.logging import logger


class EventService:
    """Business logic orchestrator for behavioral event ingestion and idempotency."""

    def __init__(self, db: Session):
        self.db = db
        self.event_repo = EventRepository(db)
        self.customer_repo = CustomerRepository(db)

    def ingest_event(self, dto: EventCreate) -> Tuple[Event, bool]:
        """
        Ingests a customer event with strict idempotency semantics:
        - If event_key exists with identical payload: returns existing event (is_new=False).
        - If event_key exists with different payload: raises 409 Conflict.
        - If new: validates customer existence, persists event, returns (event, is_new=True).
        """
        clean_key = dto.event_key.strip()
        existing = self.event_repo.get_by_key(clean_key)

        if existing:
            # Validate payload equivalence
            same_customer = existing.customer_id == dto.customer_id
            same_type = existing.event_type == dto.event_type
            same_amount = Decimal(str(existing.monetary_value)) == Decimal(str(dto.monetary_value))
            same_payload = (existing.event_payload or {}) == (dto.event_payload or {})

            if same_customer and same_type and same_amount and same_payload:
                logger.info(f"Idempotent retry detected for event_key '{clean_key}'. Returning existing record.")
                return existing, False
            else:
                logger.warning(f"Idempotency conflict detected for event_key '{clean_key}'.")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Idempotency conflict: event_key '{clean_key}' was previously ingested "
                        f"with a different payload."
                    ),
                )

        # Ensure customer exists before logging event
        customer = self.customer_repo.get_by_id(dto.customer_id)
        if not customer:
            logger.warning(f"Ingestion rejected: Customer ID {dto.customer_id} does not exist.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {dto.customer_id} not found.",
            )

        event = Event(
            event_key=clean_key,
            customer_id=dto.customer_id,
            event_type=dto.event_type,
            event_timestamp=dto.event_timestamp,
            monetary_value=dto.monetary_value,
            event_payload=dto.event_payload,
        )

        try:
            self.event_repo.create(event)
            self.db.commit()
            logger.info(f"Ingested event ID {event.id} [{event.event_type}] for customer {event.customer_id}")
            return event, True
        except Exception as exc:
            self.db.rollback()
            # Handle concurrent race condition where another worker inserted the same key
            concurrent_event = self.event_repo.get_by_key(clean_key)
            if concurrent_event:
                same_customer = concurrent_event.customer_id == dto.customer_id
                same_type = concurrent_event.event_type == dto.event_type
                same_amount = Decimal(str(concurrent_event.monetary_value)) == Decimal(str(dto.monetary_value))
                same_payload = (concurrent_event.event_payload or {}) == (dto.event_payload or {})
                if same_customer and same_type and same_amount and same_payload:
                    logger.info(f"Concurrent idempotent match resolved for event_key '{clean_key}'.")
                    return concurrent_event, False
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Idempotency conflict: event_key '{clean_key}' was previously ingested "
                            f"with a different payload."
                        ),
                    )
            logger.error(f"Failed to ingest event: {exc}")
            raise

    def get_customer_history(
        self,
        customer_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Event]:
        """Fetches chronological behavioral activity for a customer."""
        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {customer_id} not found.",
            )
        return self.event_repo.get_by_customer_id(customer_id, limit=limit, offset=offset)
