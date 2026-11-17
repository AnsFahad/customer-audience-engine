from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy import String, Numeric, DateTime, CheckConstraint, Index, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, BigIntID


class Event(Base):
    """Behavioral customer event fact entity with idempotency key support."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigIntID, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[int] = mapped_column(
        BigIntID,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    monetary_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    event_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('VIEW_PRODUCT', 'ADD_TO_CART', 'PURCHASE', 'page_view', 'product_view', 'cart_abandoned', 'purchase', 'email_open')",
            name="chk_events_valid_type",
        ),
        CheckConstraint("monetary_value >= 0", name="chk_events_monetary_positive"),
        Index("ix_events_customer_type_time", "customer_id", "event_type", "event_timestamp"),
        Index("ix_events_timestamp", "event_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, key='{self.event_key}', customer_id={self.customer_id}, type='{self.event_type}', value={self.monetary_value})>"
