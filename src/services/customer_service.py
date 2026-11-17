from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.repositories.customer_repository import CustomerRepository
from src.models.customer import Customer
from src.schemas.customer import CustomerCreate, CustomerUpdate
from src.core.logging import logger


class CustomerService:
    """Business logic orchestrator for Customer operations."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = CustomerRepository(db)

    def create_customer(self, dto: CustomerCreate) -> Customer:
        """Creates a new customer profile ensuring email uniqueness."""
        normalized_email = dto.email.lower().strip()
        existing = self.repo.get_by_email(normalized_email)
        if existing:
            logger.warning(f"Registration conflict: Customer email '{normalized_email}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with email '{normalized_email}' already exists.",
            )

        customer = Customer(
            email=normalized_email,
            first_name=dto.first_name.strip(),
            last_name=dto.last_name.strip(),
            country=dto.country.upper().strip(),
            city=dto.city.strip() if dto.city else None,
            consent_email=dto.consent_email,
            consent_sms=dto.consent_sms,
        )

        try:
            self.repo.create(customer)
            self.db.commit()
            self.db.refresh(customer)
            logger.info(f"Created customer ID {customer.id} [{customer.email}]")
            return customer
        except IntegrityError as exc:
            self.db.rollback()
            logger.warning(f"Concurrent registration conflict for email '{normalized_email}': {exc}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with email '{normalized_email}' already exists.",
            )
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to create customer: {exc}")
            raise

    def get_customer_by_id(self, customer_id: int) -> Customer:
        """Retrieves customer by primary key or raises 404."""
        customer = self.repo.get_by_id(customer_id)
        if not customer:
            logger.warning(f"Customer ID {customer_id} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {customer_id} not found.",
            )
        return customer

    def update_customer(self, customer_id: int, dto: CustomerUpdate) -> Customer:
        """Updates mutable customer profile fields and consent flags."""
        customer = self.get_customer_by_id(customer_id)

        update_data = dto.model_dump(exclude_unset=True)
        if not update_data:
            return customer

        if "first_name" in update_data and update_data["first_name"]:
            customer.first_name = update_data["first_name"].strip()
        if "last_name" in update_data and update_data["last_name"]:
            customer.last_name = update_data["last_name"].strip()
        if "city" in update_data:
            customer.city = update_data["city"].strip() if update_data["city"] else None
        if "consent_email" in update_data:
            customer.consent_email = update_data["consent_email"]
        if "consent_sms" in update_data:
            customer.consent_sms = update_data["consent_sms"]

        try:
            self.repo.update(customer)
            self.db.commit()
            self.db.refresh(customer)
            logger.info(f"Updated customer ID {customer.id}")
            return customer
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to update customer {customer_id}: {exc}")
            raise
