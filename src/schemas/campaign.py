from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from src.schemas.segment import SegmentPreviewRequest


class CampaignCreate(BaseModel):
    """Payload to create a campaign and materialize its target audience."""

    name: str = Field(..., min_length=1, max_length=150, description="Campaign name")
    description: Optional[str] = Field(None, max_length=1000, description="Campaign description")
    segment_rules: SegmentPreviewRequest = Field(
        ...,
        description="Audience segmentation filter rules to evaluate",
    )


class CampaignResponse(BaseModel):
    """Campaign presentation model."""

    id: int
    name: str
    description: Optional[str]
    status: str
    segment_rules: Dict[str, Any]
    audience_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignAudienceMemberResponse(BaseModel):
    """Enrolled audience member details."""

    customer_id: int
    email: str
    first_name: str
    last_name: str
    city: Optional[str]
    country: str
    matched_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class CampaignAudienceListResponse(BaseModel):
    """Paginated response containing campaign audience members."""

    campaign_id: int
    campaign_name: str
    total_audience_count: int
    limit: int
    offset: int
    members: List[CampaignAudienceMemberResponse]
