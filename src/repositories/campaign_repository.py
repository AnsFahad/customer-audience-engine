from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from src.models.campaign import Campaign
from src.models.campaign_audience import CampaignAudience
from src.models.customer import Customer


class CampaignRepository:
    """Data access repository for Campaigns and Materialized Campaign Audiences."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, campaign: Campaign) -> Campaign:
        """Adds a new campaign record to the session (flushed, not yet committed)."""
        self.db.add(campaign)
        self.db.flush()
        return campaign

    def get_by_id(self, campaign_id: int) -> Optional[Campaign]:
        """Fetches campaign by primary key."""
        stmt = select(Campaign).where(Campaign.id == campaign_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def bulk_insert_audience(
        self,
        campaign_id: int,
        customer_ids: List[int],
    ) -> int:
        """
        Inserts materialized customer memberships into campaign_audience.
        Composite primary key (campaign_id, customer_id) enforces uniqueness.
        """
        if not customer_ids:
            return 0

        now = datetime.now(timezone.utc)
        memberships = [
            CampaignAudience(
                campaign_id=campaign_id,
                customer_id=cid,
                matched_at=now,
                status="qualified",
            )
            for cid in customer_ids
        ]
        self.db.add_all(memberships)
        self.db.flush()
        return len(memberships)

    def get_audience_count(self, campaign_id: int) -> int:
        """Counts total materialized audience members for a campaign."""
        stmt = select(func.count(CampaignAudience.customer_id)).where(
            CampaignAudience.campaign_id == campaign_id
        )
        return self.db.execute(stmt).scalar() or 0

    def get_paginated_audience(
        self,
        campaign_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Tuple[Customer, CampaignAudience]]:
        """Fetches paginated audience members joined with customer profiles."""
        stmt = (
            select(Customer, CampaignAudience)
            .join(CampaignAudience, Customer.id == CampaignAudience.customer_id)
            .where(CampaignAudience.campaign_id == campaign_id)
            .order_by(Customer.id)
            .limit(limit)
            .offset(offset)
        )
        results = self.db.execute(stmt).all()
        return [(row[0], row[1]) for row in results]
