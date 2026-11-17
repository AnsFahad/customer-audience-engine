from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import status


def test_segment_case_insensitive_and_whitespace_category(client: TestClient):
    """Verifies that category and city matching handles leading/trailing whitespace gracefully."""
    now = datetime.now(timezone.utc)

    # Customer in 'Bengaluru'
    c_res = client.post(
        "/api/v1/customers",
        json={
            "email": "whitespace.test@example.com",
            "first_name": "White",
            "last_name": "Space",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": True,
        },
    )
    cid = c_res.json()["id"]

    # Ingest event with 'Apparel'
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_ws_{cid}",
            "customer_id": cid,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=3)).isoformat(),
            "event_payload": {"category": "Apparel"},
        },
    )

    # Query with category having leading/trailing spaces and city in lowercase
    response = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "  bengaluru  ",
            "product_category": "  Apparel  ",
            "activity_days": 10,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matching_count"] >= 1
    sample_ids = [c["id"] for c in data["sample_customers"]]
    assert cid in sample_ids


def test_segment_purchase_outside_exclusion_window_qualifies(client: TestClient):
    """
    Verifies that a customer who purchased 15 days ago qualifies when exclusion window is 14 days
    (The purchase is older than the suppression window, so they should NOT be suppressed).
    """
    now = datetime.now(timezone.utc)

    c_res = client.post(
        "/api/v1/customers",
        json={
            "email": "oldpurchase.user@example.com",
            "first_name": "Old",
            "last_name": "Purchase",
            "country": "IN",
            "consent_email": True,
        },
    )
    cid = c_res.json()["id"]

    # View 5 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_op_view_{cid}",
            "customer_id": cid,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=5)).isoformat(),
            "event_payload": {"category": "Footwear"},
        },
    )

    # Purchase 16 days ago (outside 14-day exclusion window!)
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_op_purch_{cid}",
            "customer_id": cid,
            "event_type": "PURCHASE",
            "event_timestamp": (now - timedelta(days=16)).isoformat(),
            "monetary_value": "120.00",
            "event_payload": {"category": "Footwear"},
        },
    )

    response = client.post(
        "/api/v1/segments/preview",
        json={
            "product_category": "Footwear",
            "activity_days": 30,
            "exclude_purchase_days": 14,  # Purchase was 16 days ago -> NOT suppressed!
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    sample_ids = [c["id"] for c in response.json()["sample_customers"]]
    assert cid in sample_ids


def test_segment_cross_category_isolation(client: TestClient):
    """
    Verifies that a customer with purchases in Category A ('Books') is NOT suppressed
    when evaluating a segment for Category B ('Electronics').
    """
    now = datetime.now(timezone.utc)

    c_res = client.post(
        "/api/v1/customers",
        json={
            "email": "crosscat.user@example.com",
            "first_name": "Cross",
            "last_name": "Cat",
            "country": "IN",
            "consent_email": True,
        },
    )
    cid = c_res.json()["id"]

    # Viewed Electronics 2 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_cc_view_{cid}",
            "customer_id": cid,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=2)).isoformat(),
            "event_payload": {"category": "Electronics"},
        },
    )

    # Purchased Books yesterday (different category!)
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_cc_purch_{cid}",
            "customer_id": cid,
            "event_type": "PURCHASE",
            "event_timestamp": (now - timedelta(days=1)).isoformat(),
            "monetary_value": "30.00",
            "event_payload": {"category": "Books"},
        },
    )

    # Segment for Electronics with 7-day purchase exclusion
    response = client.post(
        "/api/v1/segments/preview",
        json={
            "product_category": "Electronics",
            "activity_days": 14,
            "exclude_purchase_days": 7,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    sample_ids = [c["id"] for c in response.json()["sample_customers"]]
    # Should qualify because the purchase was for Books, not Electronics!
    assert cid in sample_ids
