from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from src.repositories.customer_repository import CustomerRepository
from src.schemas.analytics import CustomerRFMMetrics, RFMAnalyticsResponse


class AnalyticsService:
    """Domain service for customer analytics, RFM evaluation, and cohort segmentation."""

    def __init__(self, db: Session):
        self.db = db
        self.customer_repo = CustomerRepository(db)

    def calculate_rfm_analytics(
        self,
        min_spend: Optional[float] = None,
        segment_filter: Optional[str] = None,
        limit: int = 100,
    ) -> RFMAnalyticsResponse:
        """
        Calculates Recency, Frequency, and Monetary scores for customer cohort analysis.
        Categorizes profiles into actionable marketing personas.
        """
        rows = self.customer_repo.get_rfm_aggregation_data(limit=limit)
        now = datetime.now(timezone.utc)

        customer_metrics: List[CustomerRFMMetrics] = []
        cohort_counts: Dict[str, int] = {
            "Champion": 0,
            "Recent Buyer": 0,
            "At Risk": 0,
            "Engaged Prospect": 0,
            "New Lead": 0,
            "Dormant": 0,
        }
        total_revenue = 0.0

        for row in rows:
            total_events = int(row.total_events or 0)
            total_spend = float(row.total_spend or 0.0)
            last_active_at = row.last_active_at
            last_purchase_at = row.last_purchase_at

            # Calculate Recency in days
            recency_days: Optional[int] = None
            if last_active_at:
                if last_active_at.tzinfo is None:
                    last_active_at = last_active_at.replace(tzinfo=timezone.utc)
                delta = now - last_active_at
                recency_days = max(0, delta.days)

            # Assign Persona Segment
            if total_spend >= 100.0:
                if recency_days is not None and recency_days <= 30:
                    label = "Champion"
                else:
                    label = "At Risk"
            elif total_spend > 0.0:
                if recency_days is not None and recency_days <= 30:
                    label = "Recent Buyer"
                else:
                    label = "At Risk"
            elif total_events >= 2:
                if recency_days is not None and recency_days <= 30:
                    label = "Engaged Prospect"
                else:
                    label = "Dormant"
            elif total_events == 1:
                if recency_days is not None and recency_days <= 30:
                    label = "New Lead"
                else:
                    label = "Dormant"
            else:
                label = "Dormant"

            cohort_counts[label] = cohort_counts.get(label, 0) + 1
            total_revenue += total_spend

            # Optional Filtering
            if min_spend is not None and total_spend < min_spend:
                continue
            if segment_filter and label.lower() != segment_filter.lower():
                continue

            customer_metrics.append(
                CustomerRFMMetrics(
                    customer_id=row.customer_id,
                    name=f"{row.first_name} {row.last_name}".strip(),
                    email=row.email,
                    city=row.city,
                    country=row.country,
                    consent_email=row.consent_email,
                    total_events=total_events,
                    total_spend=round(total_spend, 2),
                    last_active_at=last_active_at,
                    recency_days=recency_days,
                    last_purchase_at=last_purchase_at,
                    segment_label=label,
                )
            )

        return RFMAnalyticsResponse(
            total_customers=len(customer_metrics),
            cohort_breakdown=cohort_counts,
            total_revenue=round(total_revenue, 2),
            customers=customer_metrics,
        )
