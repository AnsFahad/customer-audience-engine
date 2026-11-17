from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


ALLOWED_EVENT_TYPES = {"VIEW_PRODUCT", "ADD_TO_CART", "PURCHASE", "page_view", "product_view", "cart_abandoned", "purchase", "email_open"}


class EventCreate(BaseModel):
    """Schema for ingesting a customer behavioral event."""

    event_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique client-provided idempotency key for this event",
    )
    customer_id: int = Field(..., gt=0, description="Target customer ID")
    event_type: str = Field(..., description="Action: VIEW_PRODUCT, ADD_TO_CART, PURCHASE")
    event_timestamp: datetime = Field(
        ...,
        description="UTC timestamp when the interaction took place",
    )
    monetary_value: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Revenue associated with event (e.g. order total)",
    )
    event_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata (sku, category, device, browser, etc.)",
    )

    @field_validator("event_type")
    @classmethod
    def validate_and_normalize_event_type(cls, v: str) -> str:
        clean = v.strip()
        # Normalization mapping for common variations
        mapping = {
            "view_product": "VIEW_PRODUCT",
            "add_to_cart": "ADD_TO_CART",
            "purchase": "PURCHASE",
            "page_view": "VIEW_PRODUCT",
            "product_view": "VIEW_PRODUCT",
            "cart_abandoned": "ADD_TO_CART",
        }
        normalized = mapping.get(clean.lower(), clean.upper())
        if normalized not in {"VIEW_PRODUCT", "ADD_TO_CART", "PURCHASE"}:
            raise ValueError(
                f"Invalid event_type '{v}'. Allowed types: VIEW_PRODUCT, ADD_TO_CART, PURCHASE"
            )
        return normalized

    @field_validator("event_timestamp")
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        # Guarantee UTC timezone comparison
        now_utc = datetime.now(timezone.utc)
        target_ts = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if target_ts > now_utc:
            # Allow minor clock drift up to 60 seconds
            if (target_ts - now_utc).total_seconds() > 60:
                raise ValueError("event_timestamp cannot be in the future")
        return target_ts


class EventResponse(BaseModel):
    """Schema for event presentation output."""

    id: int
    event_key: str
    customer_id: int
    event_type: str
    event_timestamp: datetime
    monetary_value: Decimal
    event_payload: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
