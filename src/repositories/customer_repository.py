from typing import Optional, List, Tuple, Any
from sqlalchemy import select, func, case, desc
from sqlalchemy.orm import Session
from src.models.customer import Customer
from src.models.event import Event


class CustomerRepository:
    """Data access repository for Customer entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        """Fetch customer by primary key."""
        stmt = select(Customer).where(Customer.id == customer_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[Customer]:
        """Fetch customer by unique normalized email."""
        stmt = select(Customer).where(Customer.email == email.lower().strip())
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, customer: Customer) -> Customer:
        """Persist new customer record."""
        self.db.add(customer)
        self.db.flush()
        return customer

    def update(self, customer: Customer) -> Customer:
        """Mark modified customer record for persistence."""
        self.db.flush()
        return customer

    def get_rfm_aggregation_data(self, limit: int = 100) -> List[Any]:
        """
        Executes relational aggregation query across customers and events tables.
        Uses LEFT OUTER JOIN, GROUP BY, COUNT, SUM(CASE ...), and MAX.
        Returns raw rows with customer dimension fields and aggregated RFM metrics.
        """
        stmt = (
            select(
                Customer.id.label("customer_id"),
                Customer.first_name,
                Customer.last_name,
                Customer.email,
                Customer.city,
                Customer.country,
                Customer.consent_email,
                func.count(Event.id).label("total_events"),
                func.coalesce(
                    func.sum(
                        case(
                            (Event.event_type == "PURCHASE", Event.monetary_value),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_spend"),
                func.max(Event.event_timestamp).label("last_active_at"),
                func.max(
                    case(
                        (Event.event_type == "PURCHASE", Event.event_timestamp),
                        else_=None,
                    )
                ).label("last_purchase_at"),
            )
            .outerjoin(Event, Customer.id == Event.customer_id)
            .group_by(
                Customer.id,
                Customer.first_name,
                Customer.last_name,
                Customer.email,
                Customer.city,
                Customer.country,
                Customer.consent_email,
            )
            .order_by(
                desc("total_spend"),
                desc("total_events"),
            )
            .limit(limit)
        )
        return self.db.execute(stmt).all()
