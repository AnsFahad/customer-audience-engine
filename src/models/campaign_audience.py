from datetime import datetime, timezone
from sqlalchemy import String, DateTime, CheckConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, BigIntID


class CampaignAudience(Base):
    """Junction entity storing materialized campaign audience memberships with composite primary key."""

    __tablename__ = "campaign_audience"

    campaign_id: Mapped[int] = mapped_column(
        BigIntID,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    customer_id: Mapped[int] = mapped_column(
        BigIntID,
        ForeignKey("customers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="qualified",
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="audiences")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="campaign_memberships")

    __table_args__ = (
        CheckConstraint(
            "status IN ('qualified', 'sent', 'suppressed', 'failed')",
            name="chk_campaign_audience_status",
        ),
        Index("ix_campaign_audience_customer", "customer_id"),
    )

    def __repr__(self) -> str:
        return f"<CampaignAudience(campaign_id={self.campaign_id}, customer_id={self.customer_id}, status='{self.status}')>"
