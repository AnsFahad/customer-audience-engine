from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field


class CustomerRFMMetrics(BaseModel):
    """Calculated Recency, Frequency, and Monetary (RFM) metrics for a customer profile."""

    model_config = ConfigDict(from_attributes=True)

    customer_id: int
    name: str
    email: str
    city: Optional[str] = None
    country: str
    consent_email: bool
    total_events: int = Field(description="Frequency: Total interactions across all categories")
    total_spend: float = Field(description="Monetary: Total aggregate purchase spend in USD")
    last_active_at: Optional[datetime] = Field(None, description="Timestamp of most recent event")
    recency_days: Optional[int] = Field(None, description="Days elapsed since most recent activity")
    last_purchase_at: Optional[datetime] = Field(None, description="Timestamp of most recent purchase")
    segment_label: str = Field(
        description="Behavioral persona: Champion, At Risk, Engaged Prospect, New Lead, Dormant"
    )


class RFMAnalyticsResponse(BaseModel):
    """Aggregate RFM analytics report with customer breakdown and summary cohort counts."""

    total_customers: int
    cohort_breakdown: Dict[str, int] = Field(
        description="Count of customers per behavioral persona segment"
    )
    total_revenue: float = Field(description="Total cumulative revenue from all purchases")
    customers: List[CustomerRFMMetrics]
