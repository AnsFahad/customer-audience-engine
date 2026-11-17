from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from src.schemas.analytics import RFMAnalyticsResponse
from src.services.customer_service import CustomerService
from src.services.analytics_service import AnalyticsService

router = APIRouter()


@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer Profile",
)
def create_customer(
    dto: CustomerCreate,
    db: Session = Depends(get_db),
):
    """Registers a new customer profile with marketing consent preferences."""
    service = CustomerService(db)
    return service.create_customer(dto)


@router.get(
    "/customers/analytics/rfm",
    response_model=RFMAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer RFM Analytics Report",
)
def get_customer_rfm_analytics(
    min_spend: Optional[float] = Query(None, description="Filter customers with spend >= min_spend"),
    segment: Optional[str] = Query(None, description="Filter by cohort: Champion, At Risk, Engaged Prospect, New Lead, Dormant"),
    limit: int = Query(50, ge=1, le=500, description="Max number of customer rows to return"),
    db: Session = Depends(get_db),
):
    """
    Computes Recency, Frequency, and Monetary (RFM) aggregations across the customer base.
    Uses relational GROUP BY, COUNT, SUM(CASE ...), and MAX aggregations.
    Categorizes profiles into marketing personas for targeting and retention.
    """
    service = AnalyticsService(db)
    return service.calculate_rfm_analytics(
        min_spend=min_spend,
        segment_filter=segment,
        limit=limit,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer Profile by ID",
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    """Fetches single customer profile by primary key."""
    service = CustomerService(db)
    return service.get_customer_by_id(customer_id)


@router.patch(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Customer Profile",
)
def update_customer(
    customer_id: int,
    dto: CustomerUpdate,
    db: Session = Depends(get_db),
):
    """Updates mutable fields (name, city, consent) of an existing customer."""
    service = CustomerService(db)
    return service.update_customer(customer_id, dto)
