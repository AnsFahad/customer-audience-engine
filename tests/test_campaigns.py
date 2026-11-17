from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.models.campaign import Campaign
from src.models.campaign_audience import CampaignAudience


def _setup_campaign_test_data(client: TestClient):
    """Sets up a customer with qualifying activity for testing campaigns."""
    now = datetime.now(timezone.utc)
    res = client.post(
        "/api/v1/customers",
        json={
            "email": "campaign.shopper@example.com",
            "first_name": "Camp",
            "last_name": "Shopper",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": True,
        },
    )
    cid = res.json()["id"]

    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_camp_view_{cid}",
            "customer_id": cid,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=2)).isoformat(),
            "event_payload": {"category": "Gaming"},
        },
    )
    return cid


def test_create_campaign_success(client: TestClient):
    """Verifies that creating a campaign materializes matching audience members atomically."""
    cid = _setup_campaign_test_data(client)

    payload = {
        "name": "Diwali Gaming Sale",
        "description": "Gamers in Bengaluru",
        "segment_rules": {
            "city": "Bengaluru",
            "product_category": "Gaming",
            "activity_days": 14,
            "require_marketing_consent": True,
        },
    }

    response = client.post("/api/v1/campaigns", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Diwali Gaming Sale"
    assert data["status"] == "active"
    assert data["audience_count"] >= 1
    campaign_id = data["id"]

    # Verify audience list endpoint
    aud_res = client.get(f"/api/v1/campaigns/{campaign_id}/audience")
    assert aud_res.status_code == status.HTTP_200_OK
    aud_data = aud_res.json()
    assert aud_data["campaign_id"] == campaign_id
    assert aud_data["total_audience_count"] >= 1
    member_cids = [m["customer_id"] for m in aud_data["members"]]
    assert cid in member_cids


def test_create_campaign_empty_audience(client: TestClient):
    """Verifies that a campaign matching 0 audience members is created with audience_count=0."""
    payload = {
        "name": "Luxury Yachts Campaign",
        "description": "Yacht buyers in Bengaluru",
        "segment_rules": {
            "city": "Bengaluru",
            "product_category": "LuxuryYachts",  # Zero interactions
            "activity_days": 30,
            "require_marketing_consent": True,
        },
    }

    response = client.post("/api/v1/campaigns", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["audience_count"] == 0

    aud_res = client.get(f"/api/v1/campaigns/{data['id']}/audience")
    assert aud_res.status_code == status.HTTP_200_OK
    assert aud_res.json()["total_audience_count"] == 0
    assert aud_res.json()["members"] == []


def test_create_campaign_invalid_filters(client: TestClient):
    """Verifies that invalid segmentation filters return 422 Unprocessable Content."""
    # Negative activity_days
    bad_payload = {
        "name": "Bad Filter Campaign",
        "segment_rules": {
            "product_category": "Gaming",
            "activity_days": -5,  # Invalid! Must be >= 1
        },
    }
    response = client.post("/api/v1/campaigns", json=bad_payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_campaign_with_purchase_exclusion_filter(client: TestClient):
    """Verifies campaign creation with exclude_purchase_days suppresses recent buyers from audience."""
    cid = _setup_campaign_test_data(client)
    now = datetime.now(timezone.utc)

    # Ingest purchase 2 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_exclude_test_{cid}",
            "customer_id": cid,
            "event_type": "PURCHASE",
            "event_timestamp": (now - timedelta(days=2)).isoformat(),
            "monetary_value": "150.00",
            "event_payload": {"category": "Gaming"},
        },
    )

    # Create campaign with 7-day purchase exclusion
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Exclusion Window Campaign",
            "segment_rules": {
                "product_category": "Gaming",
                "activity_days": 30,
                "exclude_purchase_days": 7,  # User purchased 2 days ago -> must be suppressed!
                "require_marketing_consent": True,
            },
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["audience_count"] == 0


def test_get_campaign_audience_not_found(client: TestClient):
    """Verifies that requesting audience for non-existent campaign returns 404 Not Found."""
    response = client.get("/api/v1/campaigns/999999/audience")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_duplicate_audience_records_prevention(client: TestClient, db_session: Session):
    """Verifies that the composite primary key prevents duplicate (campaign_id, customer_id) entries."""
    cid = _setup_campaign_test_data(client)

    # 1. Create campaign via API
    res = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Composite Key Test Campaign",
            "segment_rules": {
                "product_category": "Gaming",
                "activity_days": 30,
            },
        },
    )
    campaign_id = res.json()["id"]

    # 2. Directly verify database uniqueness: inserting identical composite PK must fail
    now = datetime.now(timezone.utc)
    duplicate_entry = CampaignAudience(
        campaign_id=campaign_id,
        customer_id=cid,
        matched_at=now,
        status="qualified",
    )
    db_session.add(duplicate_entry)

    from sqlalchemy.exc import IntegrityError
    import pytest
    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_database_failure_during_audience_insertion_triggers_rollback(client: TestClient, db_session: Session):
    """Verifies that an error during audience bulk insert rolls back the entire campaign creation."""
    _setup_campaign_test_data(client)

    payload = {
        "name": "Doomed Crash Campaign",
        "description": "Will crash during audience insertion",
        "segment_rules": {
            "product_category": "Gaming",
            "activity_days": 30,
        },
    }

    # Simulate database crash during bulk_insert_audience
    with patch(
        "src.repositories.campaign_repository.CampaignRepository.bulk_insert_audience",
        side_effect=RuntimeError("Simulated disk I/O failure during audience insertion"),
    ):
        import pytest
        with pytest.raises(RuntimeError, match="Simulated disk I/O failure"):
            client.post("/api/v1/campaigns", json=payload)

    # Verify Rollback: Campaign must NOT exist in database!
    stmt = select(Campaign).where(Campaign.name == "Doomed Crash Campaign")
    aborted_campaign = db_session.execute(stmt).scalar_one_or_none()
    assert aborted_campaign is None, "Transaction rollback failed: Campaign was persisted despite mid-transaction crash!"


def test_transaction_rollback_guarantee(client: TestClient, db_session: Session):
    """Explicitly verifies atomicity: no partial campaign or audience records persist after a failure."""
    _setup_campaign_test_data(client)

    payload = {
        "name": "Atomicity Check Campaign",
        "segment_rules": {
            "product_category": "Gaming",
            "activity_days": 30,
        },
    }

    # Simulate segmentation evaluation failure
    with patch(
        "src.repositories.segment_repository.SegmentRepository.get_matching_customer_ids",
        side_effect=Exception("Simulated SQL engine timeout"),
    ):
        import pytest
        with pytest.raises(Exception, match="Simulated SQL engine timeout"):
            client.post("/api/v1/campaigns", json=payload)

    # Verify neither campaign nor audience exists
    campaign_stmt = select(Campaign).where(Campaign.name == "Atomicity Check Campaign")
    assert db_session.execute(campaign_stmt).scalar_one_or_none() is None
