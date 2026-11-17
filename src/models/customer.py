from datetime import datetime, timezone
from typing import List
from sqlalchemy import String, Boolean, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, BigIntID


class Customer(Base):
    """Customer profile dimension entity representing unified consumer identity and consent."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigIntID, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    consent_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    campaign_memberships: Mapped[List["CampaignAudience"]] = relationship(
        "CampaignAudience",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("length(country) = 2", name="chk_customers_country_length"),
        Index("ix_customers_consent_country", "consent_email", "country"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, email='{self.email}', country='{self.country}', consent_email={self.consent_email})>"
