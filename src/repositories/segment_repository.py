from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session
from src.models.customer import Customer
from src.models.event import Event


class SegmentRepository:
    """Repository executing database-level audience segmentation queries using EXISTS and NOT EXISTS."""

    def __init__(self, db: Session):
        self.db = db

    def get_matching_customer_ids(
        self,
        product_category: str,
        activity_days: int,
        city: Optional[str] = None,
        exclude_purchase_days: Optional[int] = None,
        require_marketing_consent: bool = True,
    ) -> List[int]:
        """Returns all matching customer IDs directly from the database for audience materialization."""
        now = datetime.now(timezone.utc)
        activity_cutoff = now - timedelta(days=activity_days)

        conditions = []
        if city and city.strip():
            conditions.append(func.lower(Customer.city) == city.strip().lower())

        if require_marketing_consent:
            conditions.append(Customer.consent_email.is_(True))

        activity_types = [
            "VIEW_PRODUCT",
            "ADD_TO_CART",
            "page_view",
            "product_view",
            "cart_abandoned",
        ]
        activity_subquery = exists(
            select(Event.id).where(
                Event.customer_id == Customer.id,
                Event.event_type.in_(activity_types),
                Event.event_timestamp >= activity_cutoff,
                Event.event_payload["category"].as_string() == product_category.strip(),
            )
        )
        conditions.append(activity_subquery)

        if exclude_purchase_days is not None and exclude_purchase_days > 0:
            purchase_cutoff = now - timedelta(days=exclude_purchase_days)
            purchase_types = ["PURCHASE", "purchase"]
            purchase_subquery = ~exists(
                select(Event.id).where(
                    Event.customer_id == Customer.id,
                    Event.event_type.in_(purchase_types),
                    Event.event_timestamp >= purchase_cutoff,
                    Event.event_payload["category"].as_string() == product_category.strip(),
                )
            )
            conditions.append(purchase_subquery)

        stmt = select(Customer.id).where(*conditions).order_by(Customer.id)
        return list(self.db.execute(stmt).scalars().all())

    def preview_segment(
        self,
        product_category: str,
        activity_days: int,
        city: Optional[str] = None,
        exclude_purchase_days: Optional[int] = None,
        require_marketing_consent: bool = True,
        limit: int = 20,
    ) -> Tuple[int, List[Customer]]:
        """
        Queries audience reach using PostgreSQL/relational expressions without loading events into Python:
        - Filters by City (optional)
        - Filters by Marketing Consent (consent_email = TRUE)
        - EXISTS subquery: VIEW_PRODUCT or ADD_TO_CART in category within activity_days
        - NOT EXISTS subquery: PURCHASE in category within exclude_purchase_days
        """
        now = datetime.now(timezone.utc)
        activity_cutoff = now - timedelta(days=activity_days)

        conditions = []

        # Rule 1: City Filter (Case-insensitive)
        if city and city.strip():
            conditions.append(func.lower(Customer.city) == city.strip().lower())

        # Rule 4: Marketing Consent Enforcement
        if require_marketing_consent:
            conditions.append(Customer.consent_email.is_(True))

        # Rule 2: Qualifying Activity (VIEW_PRODUCT or ADD_TO_CART) via EXISTS
        activity_types = [
            "VIEW_PRODUCT",
            "ADD_TO_CART",
            "page_view",
            "product_view",
            "cart_abandoned",
        ]
        activity_subquery = exists(
            select(Event.id).where(
                Event.customer_id == Customer.id,
                Event.event_type.in_(activity_types),
                Event.event_timestamp >= activity_cutoff,
                Event.event_payload["category"].as_string() == product_category.strip(),
            )
        )
        conditions.append(activity_subquery)

        # Rule 3: Purchase Suppression via NOT EXISTS
        if exclude_purchase_days is not None and exclude_purchase_days > 0:
            purchase_cutoff = now - timedelta(days=exclude_purchase_days)
            purchase_types = ["PURCHASE", "purchase"]
            purchase_subquery = ~exists(
                select(Event.id).where(
                    Event.customer_id == Customer.id,
                    Event.event_type.in_(purchase_types),
                    Event.event_timestamp >= purchase_cutoff,
                    Event.event_payload["category"].as_string() == product_category.strip(),
                )
            )
            conditions.append(purchase_subquery)

        # 1. Total matching count calculated directly in DB
        count_stmt = select(func.count(Customer.id)).where(*conditions)
        total_count = self.db.execute(count_stmt).scalar() or 0

        # 2. Fetch up to limit sample customer records
        sample_stmt = (
            select(Customer)
            .where(*conditions)
            .order_by(Customer.id)
            .limit(limit)
        )
        samples = list(self.db.execute(sample_stmt).scalars().all())

        return total_count, samples
