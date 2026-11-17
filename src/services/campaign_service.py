from typing import Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.repositories.campaign_repository import CampaignRepository
from src.repositories.segment_repository import SegmentRepository
from src.models.campaign import Campaign
from src.schemas.campaign import (
    CampaignCreate,
    CampaignResponse,
    CampaignAudienceMemberResponse,
    CampaignAudienceListResponse,
)
from src.core.logging import logger


class CampaignService:
    """Service layer orchestrating transactional campaign creation and audience materialization."""

    def __init__(self, db: Session):
        self.db = db
        self.campaign_repo = CampaignRepository(db)
        self.segment_repo = SegmentRepository(db)

    def create_campaign_with_audience(self, dto: CampaignCreate) -> CampaignResponse:
        """
        Executes atomic multi-table campaign creation:
        1. Validates campaign & segment filter parameters (Pydantic).
        2. Begins explicit transaction boundary.
        3. Creates and flushes Campaign record.
        4. Runs database-level audience segmentation query to retrieve matching customer IDs.
        5. Bulk inserts matching customer IDs into campaign_audience with composite PK.
        6. Commits transaction.
        If any failure occurs, executes db.rollback() to leave zero orphaned or half-populated records.
        """
        # --- TRANSACTION BOUNDARY START ---
        try:
            # Step 3: Insert Campaign entity
            campaign = Campaign(
                name=dto.name.strip(),
                description=dto.description.strip() if dto.description else None,
                status="active",
                segment_rules=dto.segment_rules.model_dump(),
            )
            self.campaign_repo.create(campaign)

            # Step 4: Evaluate segmentation query in the database
            rules = dto.segment_rules
            matching_ids = self.segment_repo.get_matching_customer_ids(
                product_category=rules.product_category,
                activity_days=rules.activity_days,
                city=rules.city,
                exclude_purchase_days=rules.exclude_purchase_days,
                require_marketing_consent=rules.require_marketing_consent,
            )

            # Step 5: Save matching customer IDs in campaign_audience
            inserted_count = self.campaign_repo.bulk_insert_audience(
                campaign_id=campaign.id,
                customer_ids=matching_ids,
            )

            # Step 6: Commit transaction to disk
            self.db.commit()
            self.db.refresh(campaign)

            logger.info(
                f"Transaction committed: Campaign '{campaign.name}' (ID: {campaign.id}) "
                f"created with {inserted_count} materialized audience members."
            )

            return CampaignResponse(
                id=campaign.id,
                name=campaign.name,
                description=campaign.description,
                status=campaign.status,
                segment_rules=campaign.segment_rules,
                audience_count=inserted_count,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
            )

        except Exception as exc:
            # --- TRANSACTION ROLLBACK BOUNDARY ---
            self.db.rollback()
            logger.error(
                f"Transaction failed during campaign creation: {exc}. Rolling back changes."
            )
            raise

    def get_campaign_audience(
        self,
        campaign_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> CampaignAudienceListResponse:
        """Retrieves paginated materialized audience members for a campaign."""
        campaign = self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            logger.warning(f"Campaign ID {campaign_id} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID {campaign_id} not found.",
            )

        total_count = self.campaign_repo.get_audience_count(campaign_id)
        rows = self.campaign_repo.get_paginated_audience(
            campaign_id=campaign_id,
            limit=limit,
            offset=offset,
        )

        members = [
            CampaignAudienceMemberResponse(
                customer_id=cust.id,
                email=cust.email,
                first_name=cust.first_name,
                last_name=cust.last_name,
                city=cust.city,
                country=cust.country,
                matched_at=membership.matched_at,
                status=membership.status,
            )
            for cust, membership in rows
        ]

        return CampaignAudienceListResponse(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_audience_count=total_count,
            limit=limit,
            offset=offset,
            members=members,
        )
