from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from src.models.event import Event


class EventRepository:
    """Data access repository for Event entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, event_key: str) -> Optional[Event]:
        """Fetch event by unique idempotency key."""
        stmt = select(Event).where(Event.event_key == event_key.strip())
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, event: Event) -> Event:
        """Persist new event record."""
        self.db.add(event)
        self.db.flush()
        return event

    def get_by_customer_id(
        self,
        customer_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Event]:
        """Fetch paginated chronological events for a specific customer."""
        stmt = (
            select(Event)
            .where(Event.customer_id == customer_id)
            .order_by(desc(Event.event_timestamp))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())
