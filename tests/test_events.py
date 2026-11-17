from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from fastapi import status


def _create_sample_customer(client: TestClient, email: str = "event.user@example.com") -> int:
    res = client.post(
        "/api/v1/customers",
        json={
            "email": email,
            "first_name": "Event",
            "last_name": "Tester",
            "country": "IN",
            "consent_email": True,
        },
    )
    return res.json()["id"]


def test_ingest_event_types_success(client: TestClient):
    """Verifies ingesting VIEW_PRODUCT, ADD_TO_CART, and PURCHASE returns 201 Created."""
    customer_id = _create_sample_customer(client, "types.test@example.com")
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. VIEW_PRODUCT
    view_res = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_view_001",
            "customer_id": customer_id,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": now_iso,
            "monetary_value": "0.00",
            "event_payload": {"sku": "PHONE-10", "category": "Electronics"},
        },
    )
    assert view_res.status_code == status.HTTP_201_CREATED
    assert view_res.json()["event_type"] == "VIEW_PRODUCT"

    # 2. ADD_TO_CART
    cart_res = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_cart_001",
            "customer_id": customer_id,
            "event_type": "ADD_TO_CART",
            "event_timestamp": now_iso,
            "monetary_value": "0.00",
            "event_payload": {"sku": "PHONE-10", "quantity": 1},
        },
    )
    assert cart_res.status_code == status.HTTP_201_CREATED
    assert cart_res.json()["event_type"] == "ADD_TO_CART"

    # 3. PURCHASE
    purchase_res = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_purchase_001",
            "customer_id": customer_id,
            "event_type": "PURCHASE",
            "event_timestamp": now_iso,
            "monetary_value": "199.99",
            "event_payload": {"order_id": "ORD-99", "items": 1},
        },
    )
    assert purchase_res.status_code == status.HTTP_201_CREATED
    assert purchase_res.json()["event_type"] == "PURCHASE"
    assert Decimal(str(purchase_res.json()["monetary_value"])) == Decimal("199.99")


def test_idempotent_event_ingestion_duplicate_retry(client: TestClient):
    """Verifies that re-submitting an identical event with the same event_key returns 200 OK without creating duplicate."""
    customer_id = _create_sample_customer(client, "idempotent.test@example.com")
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "event_key": "evt_unique_101",
        "customer_id": customer_id,
        "event_type": "PURCHASE",
        "event_timestamp": now_iso,
        "monetary_value": "50.00",
        "event_payload": {"order_id": "ORD-50"},
    }

    # Initial request -> 201 Created
    res1 = client.post("/api/v1/events", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED
    event_id1 = res1.json()["id"]

    # Identical replay -> 200 OK (Idempotent response)
    res2 = client.post("/api/v1/events", json=payload)
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["id"] == event_id1

    # Verify customer only has 1 event in history
    history_res = client.get(f"/api/v1/customers/{customer_id}/events")
    assert history_res.status_code == status.HTTP_200_OK
    events = history_res.json()
    assert len(events) == 1


def test_idempotent_event_key_reuse_different_payload_conflict(client: TestClient):
    """Verifies that reusing an event_key with a DIFFERENT payload returns 409 Conflict."""
    customer_id = _create_sample_customer(client, "conflict.test@example.com")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Initial request
    res1 = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_conflict_key_999",
            "customer_id": customer_id,
            "event_type": "PURCHASE",
            "event_timestamp": now_iso,
            "monetary_value": "100.00",
            "event_payload": {"order_id": "ORD-100"},
        },
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # Conflict request: same event_key, DIFFERENT monetary_value
    res2 = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_conflict_key_999",
            "customer_id": customer_id,
            "event_type": "PURCHASE",
            "event_timestamp": now_iso,
            "monetary_value": "200.00",  # Different amount!
            "event_payload": {"order_id": "ORD-100"},
        },
    )
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "Idempotency conflict" in res2.json()["detail"]


def test_ingest_event_nonexistent_customer(client: TestClient):
    """Verifies that ingesting an event for a non-existent customer returns 404 Not Found."""
    now_iso = datetime.now(timezone.utc).isoformat()
    res = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_orphan_001",
            "customer_id": 888888,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": now_iso,
            "monetary_value": "0.00",
        },
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_get_customer_activity_history(client: TestClient):
    """Verifies fetching activity history returns events sorted by timestamp in reverse order."""
    customer_id = _create_sample_customer(client, "history.test@example.com")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Ingest 2 events
    client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_hist_1",
            "customer_id": customer_id,
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": now_iso,
            "monetary_value": "0.00",
        },
    )
    client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_hist_2",
            "customer_id": customer_id,
            "event_type": "PURCHASE",
            "event_timestamp": now_iso,
            "monetary_value": "75.00",
        },
    )

    history_res = client.get(f"/api/v1/customers/{customer_id}/events")
    assert history_res.status_code == status.HTTP_200_OK
    events = history_res.json()
    assert len(events) == 2


def test_event_validation_errors(client: TestClient):
    """Verifies that invalid event_type or negative monetary value triggers 422 Unprocessable Entity."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # Invalid event_type
    res1 = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_bad_type",
            "customer_id": 1,
            "event_type": "INVALID_ACTION",
            "event_timestamp": now_iso,
        },
    )
    assert res1.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Negative monetary value
    res2 = client.post(
        "/api/v1/events",
        json={
            "event_key": "evt_neg_money",
            "customer_id": 1,
            "event_type": "PURCHASE",
            "event_timestamp": now_iso,
            "monetary_value": "-10.00",
        },
    )
    assert res2.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
