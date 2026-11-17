from datetime import datetime, timezone
import concurrent.futures
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from src.models.event import Event
from src.models.customer import Customer


def test_concurrent_identical_event_ingestion(client: TestClient, db_session: Session):
    """
    Simulates high-concurrency race condition:
    10 threads simultaneously send identical event_key and payload to /api/v1/events.
    Verifies that:
    - Every request succeeds with 201 (initial) or 200 (idempotent replay).
    - Exactly ONE row is persisted in the database.
    - No 500 errors or unhandled exceptions occur.
    """
    # Create customer
    c_res = client.post(
        "/api/v1/customers",
        json={
            "email": "concurrency.user@example.com",
            "first_name": "Concurrent",
            "last_name": "User",
            "country": "IN",
            "consent_email": True,
        },
    )
    cid = c_res.json()["id"]

    now_iso = datetime.now(timezone.utc).isoformat()
    shared_key = f"evt_concurrent_race_{cid}"
    payload = {
        "event_key": shared_key,
        "customer_id": cid,
        "event_type": "PURCHASE",
        "event_timestamp": now_iso,
        "monetary_value": "99.00",
        "event_payload": {"order_id": "ORD-RACE-1"},
    }

    results = []

    def send_request():
        # Each thread uses client
        return client.post("/api/v1/events", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_request) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Verify all responses are 201 (winner) or 200 (idempotent replay)
    status_codes = [r.status_code for r in results]
    assert all(code in (status.HTTP_201_CREATED, status.HTTP_200_OK) for code in status_codes)
    assert status.HTTP_201_CREATED in status_codes

    # Verify that exactly ONE event row exists in the database
    stmt = select(func.count(Event.id)).where(Event.event_key == shared_key)
    count = db_session.execute(stmt).scalar()
    assert count == 1, f"Concurrency failure: Expected exactly 1 row, found {count}!"


def test_concurrent_duplicate_customer_registration(client: TestClient, db_session: Session):
    """
    Simulates concurrent customer registration with identical email.
    Verifies that one request succeeds with 201 Created and others return 409 Conflict.
    No 500 errors are produced.
    """
    payload = {
        "email": "race.customer@example.com",
        "first_name": "Race",
        "last_name": "Customer",
        "country": "US",
        "consent_email": True,
    }

    results = []

    def register():
        return client.post("/api/v1/customers", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(register) for _ in range(8)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    status_codes = [r.status_code for r in results]
    assert status.HTTP_201_CREATED in status_codes
    assert all(code in (status.HTTP_201_CREATED, status.HTTP_409_CONFLICT) for code in status_codes)

    # Exactly one customer exists with this email
    stmt = select(func.count(Customer.id)).where(Customer.email == "race.customer@example.com")
    count = db_session.execute(stmt).scalar()
    assert count == 1
