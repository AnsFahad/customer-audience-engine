from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy import String, Text, DateTime, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, BigIntID


class Campaign(Base):
    """Marketing campaign entity with declarative audience segmentation criteria."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigIntID, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    segment_rules: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    audiences: Mapped[List["CampaignAudience"]] = relationship(
        "CampaignAudience",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'completed')",
            name="chk_campaigns_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Campaign(id={self.id}, name='{self.name}', status='{self.status}')>"
