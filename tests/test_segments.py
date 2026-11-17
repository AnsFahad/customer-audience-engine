from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import status


def _setup_segmentation_fixtures(client: TestClient):
    """Sets up a controlled cohort of 5 customers with distinct behavioral profiles."""
    now = datetime.now(timezone.utc)

    # 1. User 1: Fully Qualifying User in Bengaluru
    u1 = client.post(
        "/api/v1/customers",
        json={
            "email": "user1.qualifying@test.com",
            "first_name": "Rohan",
            "last_name": "Mehta",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": True,
        },
    ).json()["id"]

    # 2. User 2: Wrong City User in Mumbai
    u2 = client.post(
        "/api/v1/customers",
        json={
            "email": "user2.mumbai@test.com",
            "first_name": "Aarav",
            "last_name": "Shah",
            "country": "IN",
            "city": "Mumbai",
            "consent_email": True,
        },
    ).json()["id"]

    # 3. User 3: In Bengaluru, but no qualifying activity in Electronics
    u3 = client.post(
        "/api/v1/customers",
        json={
            "email": "user3.noactivity@test.com",
            "first_name": "Kavita",
            "last_name": "Rao",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": True,
        },
    ).json()["id"]

    # 4. User 4: In Bengaluru, viewed Electronics, but RECENTLY PURCHASED Electronics
    u4 = client.post(
        "/api/v1/customers",
        json={
            "email": "user4.recentpurchaser@test.com",
            "first_name": "Vikram",
            "last_name": "Das",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": True,
        },
    ).json()["id"]

    # 5. User 5: In Bengaluru, viewed Electronics, NO purchase, but NO MARKETING CONSENT
    u5 = client.post(
        "/api/v1/customers",
        json={
            "email": "user5.noconsent@test.com",
            "first_name": "Sneha",
            "last_name": "Nair",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": False,  # No consent!
        },
    ).json()["id"]

    # Ingest activity events
    # U1: Viewed Electronics 5 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_u1_view_{u1}",
            "customer_id": u1,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=5)).isoformat(),
            "event_payload": {"category": "Electronics"},
        },
    )

    # U2: Viewed Electronics 5 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_u2_view_{u2}",
            "customer_id": u2,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=5)).isoformat(),
            "event_payload": {"category": "Electronics"},
        },
    )

    # U4: Viewed Electronics 8 days ago AND Purchased Electronics 2 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_u4_view_{u4}",
            "customer_id": u4,
            "event_type": "ADD_TO_CART",
            "event_timestamp": (now - timedelta(days=8)).isoformat(),
            "event_payload": {"category": "Electronics"},
        },
    )
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_u4_purchase_{u4}",
            "customer_id": u4,
            "event_type": "PURCHASE",
            "event_timestamp": (now - timedelta(days=2)).isoformat(),
            "monetary_value": "150.00",
            "event_payload": {"category": "Electronics"},
        },
    )

    # U5: Viewed Electronics 4 days ago
    client.post(
        "/api/v1/events",
        json={
            "event_key": f"evt_u5_view_{u5}",
            "customer_id": u5,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": (now - timedelta(days=4)).isoformat(),
            "event_payload": {"category": "Electronics"},
        },
    )

    return {"u1": u1, "u2": u2, "u3": u3, "u4": u4, "u5": u5}


def test_segment_matching_customers(client: TestClient):
    """Verifies that customers matching city, activity, consent, and no recent purchase qualify."""
    users = _setup_segmentation_fixtures(client)

    response = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "Electronics",
            "activity_days": 30,
            "exclude_purchase_days": 14,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matching_count"] >= 1
    sample_ids = [c["id"] for c in data["sample_customers"]]
    assert users["u1"] in sample_ids
    # User 4 (recent purchaser) and User 5 (no consent) must not be in the list
    assert users["u4"] not in sample_ids
    assert users["u5"] not in sample_ids


def test_segment_wrong_city(client: TestClient):
    """Verifies that filtering by an unmatched city excludes candidates."""
    users = _setup_segmentation_fixtures(client)

    response = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Chennai",  # No users in Chennai
            "product_category": "Electronics",
            "activity_days": 30,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matching_count"] == 0
    assert len(data["sample_customers"]) == 0


def test_segment_no_qualifying_activity(client: TestClient):
    """Verifies that customers without activity in the target category are not matched."""
    _setup_segmentation_fixtures(client)

    response = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "HomeImprovement",  # Category with no events
            "activity_days": 30,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matching_count"] == 0
    assert len(data["sample_customers"]) == 0


def test_segment_recent_purchasers_suppressed(client: TestClient):
    """Verifies that recent purchasers are excluded when exclude_purchase_days is provided."""
    users = _setup_segmentation_fixtures(client)

    # With exclude_purchase_days=14: U4 is suppressed
    res_suppressed = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "Electronics",
            "activity_days": 30,
            "exclude_purchase_days": 14,
            "require_marketing_consent": True,
        },
    )
    assert res_suppressed.status_code == status.HTTP_200_OK
    sample_ids = [c["id"] for c in res_suppressed.json()["sample_customers"]]
    assert users["u4"] not in sample_ids

    # Without exclude_purchase_days (None): U4 qualifies!
    res_unsuppressed = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "Electronics",
            "activity_days": 30,
            "exclude_purchase_days": None,
            "require_marketing_consent": True,
        },
    )
    assert res_unsuppressed.status_code == status.HTTP_200_OK
    unsuppressed_ids = [c["id"] for c in res_unsuppressed.json()["sample_customers"]]
    assert users["u4"] in unsuppressed_ids


def test_segment_customers_without_consent(client: TestClient):
    """Verifies that customers without consent are excluded when require_marketing_consent=True, but included when False."""
    users = _setup_segmentation_fixtures(client)

    # When require_marketing_consent=True -> U5 is excluded
    res_strict = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "Electronics",
            "activity_days": 30,
            "require_marketing_consent": True,
        },
    )
    strict_ids = [c["id"] for c in res_strict.json()["sample_customers"]]
    assert users["u5"] not in strict_ids

    # When require_marketing_consent=False -> U5 qualifies
    res_lax = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "Bengaluru",
            "product_category": "Electronics",
            "activity_days": 30,
            "require_marketing_consent": False,
        },
    )
    lax_ids = [c["id"] for c in res_lax.json()["sample_customers"]]
    assert users["u5"] in lax_ids


def test_segment_empty_result(client: TestClient):
    """Verifies that filters matching zero customers return count=0 and empty sample list."""
    response = client.post(
        "/api/v1/segments/preview",
        json={
            "city": "NonExistentCity",
            "product_category": "NonExistentCategory",
            "activity_days": 1,
            "require_marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matching_count"] == 0
    assert data["sample_customers"] == []
    assert data["applied_filters"]["city"] == "NonExistentCity"
