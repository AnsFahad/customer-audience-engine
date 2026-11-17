"""Deterministic synthetic seed data script for Customer Data & Audience Segmentation Engine."""

import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from src.core.database import SessionLocal
from src.models import Customer, Event, Campaign, CampaignAudience
from src.core.logging import logger


def seed_database():
    """Seeds the database with deterministic customer profiles, events, and campaigns."""
    session = SessionLocal()
    try:
        # Check if data already exists
        if session.query(Customer).first():
            logger.info("Database already seeded. Skipping seed execution.")
            return

        now = datetime.now(timezone.utc)

        logger.info("Seeding customers...")
        customers = [
            Customer(
                email="rahul.verma@example.com",
                first_name="Rahul",
                last_name="Verma",
                country="IN",
                city="Bengaluru",
                consent_email=True,
                consent_sms=False,
                created_at=now - timedelta(days=60),
            ),
            Customer(
                email="priya.sharma@example.com",
                first_name="Priya",
                last_name="Sharma",
                country="IN",
                city="Mumbai",
                consent_email=False,  # NO email consent! Must be suppressed by email campaigns
                consent_sms=True,
                created_at=now - timedelta(days=45),
            ),
            Customer(
                email="john.doe@example.com",
                first_name="John",
                last_name="Doe",
                country="US",
                city="New York",
                consent_email=True,
                consent_sms=True,
                created_at=now - timedelta(days=30),
            ),
            Customer(
                email="sarah.connor@example.com",
                first_name="Sarah",
                last_name="Connor",
                country="US",
                city="Austin",
                consent_email=True,
                consent_sms=False,
                created_at=now - timedelta(days=20),
            ),
            Customer(
                email="amit.patel@example.com",
                first_name="Amit",
                last_name="Patel",
                country="IN",
                city="Delhi",
                consent_email=True,
                consent_sms=True,
                created_at=now - timedelta(days=15),
            ),
        ]
        session.add_all(customers)
        session.flush()  # Populates customer IDs

        c_rahul = customers[0]
        c_priya = customers[1]
        c_john = customers[2]
        c_sarah = customers[3]
        c_amit = customers[4]

        logger.info("Seeding behavioral events...")
        events = [
            # Rahul's events: total purchase spend = $90.00 + $85.50 = $175.50 (Qualifies for IN VIP!)
            Event(
                event_key="evt_seed_rahul_001",
                customer_id=c_rahul.id,
                event_type="page_view",
                event_timestamp=now - timedelta(days=18),
                monetary_value=Decimal("0.00"),
                event_payload={"category": "Electronics", "device": "mobile"},
            ),
            Event(
                event_key="evt_seed_rahul_002",
                customer_id=c_rahul.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=14),
                monetary_value=Decimal("90.00"),
                event_payload={"order_id": "ORD-101", "category": "Electronics"},
            ),
            Event(
                event_key="evt_seed_rahul_003",
                customer_id=c_rahul.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=6),
                monetary_value=Decimal("85.50"),
                event_payload={"order_id": "ORD-102", "category": "Electronics"},
            ),
            Event(
                event_key="evt_seed_rahul_004",
                customer_id=c_rahul.id,
                event_type="cart_abandoned",
                event_timestamp=now - timedelta(days=1),
                monetary_value=Decimal("0.00"),
                event_payload={"sku": "HEADPHONE-Z"},
            ),
            # Priya's events: spend = $320.00, BUT consent_email=False (Consent test case!)
            Event(
                event_key="evt_seed_priya_001",
                customer_id=c_priya.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=5),
                monetary_value=Decimal("320.00"),
                event_payload={"order_id": "ORD-201", "category": "Fashion"},
            ),
            # John's events: spend = $45.00 (Below spend threshold of $150/$200)
            Event(
                event_key="evt_seed_john_001",
                customer_id=c_john.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=8),
                monetary_value=Decimal("45.00"),
                event_payload={"order_id": "ORD-301", "category": "Books"},
            ),
            # Sarah's events: spend = $250.00 in US (Qualifies for US campaign)
            Event(
                event_key="evt_seed_sarah_001",
                customer_id=c_sarah.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=10),
                monetary_value=Decimal("250.00"),
                event_payload={"order_id": "ORD-401", "category": "Home"},
            ),
            # Amit's events: spend = $210.00 in IN with consent (Qualifies for IN VIP!)
            Event(
                event_key="evt_seed_amit_001",
                customer_id=c_amit.id,
                event_type="purchase",
                event_timestamp=now - timedelta(days=3),
                monetary_value=Decimal("210.00"),
                event_payload={"order_id": "ORD-501", "category": "Electronics"},
            ),
        ]
        session.add_all(events)

        logger.info("Seeding marketing campaigns...")
        campaigns = [
            Campaign(
                name="Diwali VIP Electronics Shoppers",
                description="High-value shoppers in India who spent at least $150 in the last 30 days",
                status="active",
                segment_rules={
                    "country": "IN",
                    "channel": "email",
                    "event_filters": {
                        "event_type": "purchase",
                        "min_total_spend": 150.00,
                        "days_window": 30,
                    },
                },
            ),
            Campaign(
                name="US High-Value Shoppers",
                description="US shoppers who spent at least $200 in the last 60 days",
                status="draft",
                segment_rules={
                    "country": "US",
                    "channel": "email",
                    "event_filters": {
                        "event_type": "purchase",
                        "min_total_spend": 200.00,
                        "days_window": 60,
                    },
                },
            ),
        ]
        session.add_all(campaigns)
        session.flush()

        logger.info("Materializing sample campaign audience membership...")
        # Rahul and Amit qualify for Campaign 1 (Diwali VIP)
        memberships = [
            CampaignAudience(
                campaign_id=campaigns[0].id,
                customer_id=c_rahul.id,
                matched_at=now,
                status="qualified",
            ),
            CampaignAudience(
                campaign_id=campaigns[0].id,
                customer_id=c_amit.id,
                matched_at=now,
                status="qualified",
            ),
            # Sarah qualifies for Campaign 2 (US High-Value)
            CampaignAudience(
                campaign_id=campaigns[1].id,
                customer_id=c_sarah.id,
                matched_at=now,
                status="qualified",
            ),
        ]
        session.add_all(memberships)

        session.commit()
        logger.info("Database successfully seeded with deterministic test records!")

    except Exception as exc:
        session.rollback()
        logger.error(f"Seeding failed: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
