from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.schemas.campaign import (
    CampaignCreate,
    CampaignResponse,
    CampaignAudienceListResponse,
)
from src.services.campaign_service import CampaignService

router = APIRouter()


@router.post(
    "/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Campaign & Materialize Audience Atomically",
)
def create_campaign(
    dto: CampaignCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new campaign, queries its audience, and materializes all matching customers
    into campaign_audience within a single atomic database transaction.
    Rolls back completely if any failure occurs.
    """
    service = CampaignService(db)
    return service.create_campaign_with_audience(dto)


@router.get(
    "/campaigns/{campaign_id}/audience",
    response_model=CampaignAudienceListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Materialized Campaign Audience",
)
def get_campaign_audience(
    campaign_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated audience members for a campaign."""
    service = CampaignService(db)
    return service.get_campaign_audience(
        campaign_id=campaign_id,
        limit=limit,
        offset=offset,
    )
