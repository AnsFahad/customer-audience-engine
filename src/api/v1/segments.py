from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.schemas.segment import SegmentPreviewRequest, SegmentPreviewResponse
from src.services.segment_service import SegmentService

router = APIRouter()


@router.post(
    "/segments/preview",
    response_model=SegmentPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview Dynamic Audience Segment",
)
def preview_segment(
    dto: SegmentPreviewRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates dynamic audience criteria using database-level EXISTS and NOT EXISTS:
    1. Matches optional City.
    2. Must have VIEW_PRODUCT or ADD_TO_CART activity within activity_days.
    3. Excludes customers with PURCHASE activity within exclude_purchase_days (if provided).
    4. Enforces marketing_consent = true when require_marketing_consent is set.
    """
    service = SegmentService(db)
    return service.preview_segment(dto)
