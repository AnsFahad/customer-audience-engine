from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class SegmentPreviewRequest(BaseModel):
    """Filters used to define dynamic audience cohort criteria."""

    city: Optional[str] = Field(
        None,
        description="Optional city filter (e.g. 'Bengaluru', 'Mumbai', 'New York')",
    )
    product_category: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target category (e.g. 'Electronics', 'Fashion', 'Home')",
    )
    activity_days: int = Field(
        ...,
        ge=1,
        le=365,
        description="Window in days to look for VIEW_PRODUCT or ADD_TO_CART activity",
    )
    exclude_purchase_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Optional suppression window: exclude users who bought from this category recently",
    )
    require_marketing_consent: bool = Field(
        default=True,
        description="If True, customer must have consent_email = True to be eligible",
    )


class SegmentFilterSummary(BaseModel):
    """Echo of the filters applied during audience segmentation."""

    city: Optional[str] = None
    product_category: str
    activity_days: int
    exclude_purchase_days: Optional[int] = None
    require_marketing_consent: bool


class SegmentCustomerSample(BaseModel):
    """Summary customer DTO returned in preview samples."""

    id: int
    email: str
    first_name: str
    last_name: str
    city: Optional[str]
    country: str
    consent_email: bool

    model_config = ConfigDict(from_attributes=True)


class SegmentPreviewResponse(BaseModel):
    """Preview response containing total matching count and up to 20 customer samples."""

    matching_count: int
    sample_customers: List[SegmentCustomerSample]
    applied_filters: SegmentFilterSummary
