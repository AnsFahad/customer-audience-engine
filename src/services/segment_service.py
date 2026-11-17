from sqlalchemy.orm import Session
from src.repositories.segment_repository import SegmentRepository
from src.schemas.segment import (
    SegmentPreviewRequest,
    SegmentPreviewResponse,
    SegmentFilterSummary,
    SegmentCustomerSample,
)
from src.core.logging import logger


class SegmentService:
    """Service layer orchestrating audience cohort evaluations and filter summaries."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = SegmentRepository(db)

    def preview_segment(self, dto: SegmentPreviewRequest) -> SegmentPreviewResponse:
        """Evaluates segment filter criteria and returns reach count with sample customers."""
        logger.info(
            f"Evaluating segment preview: category='{dto.product_category}', "
            f"city={dto.city}, activity_days={dto.activity_days}, "
            f"exclude_purchase_days={dto.exclude_purchase_days}, consent={dto.require_marketing_consent}"
        )

        total_count, sample_records = self.repo.preview_segment(
            product_category=dto.product_category,
            activity_days=dto.activity_days,
            city=dto.city,
            exclude_purchase_days=dto.exclude_purchase_days,
            require_marketing_consent=dto.require_marketing_consent,
            limit=20,
        )

        sample_dtos = [SegmentCustomerSample.model_validate(c) for c in sample_records]

        filter_summary = SegmentFilterSummary(
            city=dto.city,
            product_category=dto.product_category,
            activity_days=dto.activity_days,
            exclude_purchase_days=dto.exclude_purchase_days,
            require_marketing_consent=dto.require_marketing_consent,
        )

        return SegmentPreviewResponse(
            matching_count=total_count,
            sample_customers=sample_dtos,
            applied_filters=filter_summary,
        )
