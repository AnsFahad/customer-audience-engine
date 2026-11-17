from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import status


def _create_customer_with_events(
    client: TestClient,
    email: str,
    first_name: str,
    city: str,
    events_data: list,
) -> int:
    """Helper to create a customer and ingest multiple events for RFM evaluation."""
    res = client.post(
        "/api/v1/customers",
        json={
            "email": email,
            "first_name": first_name,
            "last_name": "Tester",
            "country": "IN",
            "city": city,
            "consent_email": True,
        },
    )
    assert res.status_code == status.HTTP_201_CREATED
    cid = res.json()["id"]

    for idx, (etype, days_ago, amount) in enumerate(events_data):
        ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
        event_res = client.post(
            "/api/v1/events",
            json={
                "event_key": f"evt_rfm_{cid}_{idx}_{etype.lower()}",
                "customer_id": cid,
                "event_type": etype,
                "event_timestamp": ts.isoformat(),
                "monetary_value": amount,
                "event_payload": {"category": "Electronics"},
            },
        )
        assert event_res.status_code == status.HTTP_201_CREATED

    return cid


def test_rfm_analytics_empty_database(client: TestClient):
    """Verifies RFM endpoint handles empty database gracefully."""
    res = client.get("/api/v1/customers/analytics/rfm")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_customers"] == 0
    assert data["total_revenue"] == 0.0
    assert len(data["customers"]) == 0
    assert data["cohort_breakdown"]["Champion"] == 0


def test_rfm_analytics_persona_assignment(client: TestClient):
    """
    Verifies that RFM analytics accurately calculates Recency, Frequency,
    and Monetary metrics, and assigns correct marketing personas:
    1. Champion: Total spend >= 100 and active <= 30 days
    2. At Risk: Total spend > 0 but inactive > 30 days
    3. Engaged Prospect: Total spend == 0, events >= 2, active <= 30 days
    4. Dormant: 0 events
    """
    # 1. Champion: $250 purchase 5 days ago
    cid_champ = _create_customer_with_events(
        client,
        email="champion@example.com",
        first_name="Alice",
        city="Bengaluru",
        events_data=[
            ("VIEW_PRODUCT", 6, 0.0),
            ("PURCHASE", 5, 250.0),
        ],
    )

    # 2. At Risk: $150 purchase 45 days ago (no recent activity)
    cid_risk = _create_customer_with_events(
        client,
        email="atrisk@example.com",
        first_name="Bob",
        city="Mumbai",
        events_data=[
            ("PURCHASE", 45, 150.0),
        ],
    )

    # 3. Engaged Prospect: 3 views/cart additions, $0 spend, active 3 days ago
    cid_prospect = _create_customer_with_events(
        client,
        email="prospect@example.com",
        first_name="Charlie",
        city="Bengaluru",
        events_data=[
            ("VIEW_PRODUCT", 10, 0.0),
            ("ADD_TO_CART", 3, 0.0),
        ],
    )

    # 4. Dormant: 0 events
    res_dormant = client.post(
        "/api/v1/customers",
        json={
            "email": "dormant@example.com",
            "first_name": "Dave",
            "last_name": "Dormant",
            "country": "IN",
            "city": "Delhi",
            "consent_email": True,
        },
    )
    cid_dormant = res_dormant.json()["id"]

    # Execute RFM endpoint
    res = client.get("/api/v1/customers/analytics/rfm")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_customers"] == 4
    assert data["total_revenue"] == 400.0  # 250 + 150

    cohorts = data["cohort_breakdown"]
    assert cohorts["Champion"] == 1
    assert cohorts["At Risk"] == 1
    assert cohorts["Engaged Prospect"] == 1
    assert cohorts["Dormant"] == 1

    # Verify individual customer metrics
    customer_map = {c["customer_id"]: c for c in data["customers"]}

    # Verify Alice (Champion)
    alice = customer_map[cid_champ]
    assert alice["name"] == "Alice Tester"
    assert alice["total_events"] == 2
    assert alice["total_spend"] == 250.0
    assert alice["segment_label"] == "Champion"
    assert alice["recency_days"] == 5

    # Verify Bob (At Risk)
    bob = customer_map[cid_risk]
    assert bob["total_events"] == 1
    assert bob["total_spend"] == 150.0
    assert bob["segment_label"] == "At Risk"
    assert bob["recency_days"] == 45

    # Verify Charlie (Engaged Prospect)
    charlie = customer_map[cid_prospect]
    assert charlie["total_events"] == 2
    assert charlie["total_spend"] == 0.0
    assert charlie["segment_label"] == "Engaged Prospect"
    assert charlie["recency_days"] == 3

    # Verify Dave (Dormant)
    dave = customer_map[cid_dormant]
    assert dave["total_events"] == 0
    assert dave["total_spend"] == 0.0
    assert dave["segment_label"] == "Dormant"
    assert dave["recency_days"] is None


def test_rfm_analytics_min_spend_filter(client: TestClient):
    """Verifies min_spend query parameter filters customer rows appropriately."""
    _create_customer_with_events(
        client,
        email="rich@example.com",
        first_name="Rich",
        city="Mumbai",
        events_data=[("PURCHASE", 2, 500.0)],
    )
    _create_customer_with_events(
        client,
        email="lowspend@example.com",
        first_name="Low",
        city="Mumbai",
        events_data=[("PURCHASE", 2, 20.0)],
    )

    res = client.get("/api/v1/customers/analytics/rfm?min_spend=100")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_customers"] == 1
    assert data["customers"][0]["name"] == "Rich Tester"
    assert data["customers"][0]["total_spend"] == 500.0


def test_rfm_analytics_segment_filter(client: TestClient):
    """Verifies segment query parameter filters by cohort label."""
    _create_customer_with_events(
        client,
        email="lead@example.com",
        first_name="New",
        city="Mumbai",
        events_data=[("VIEW_PRODUCT", 1, 0.0)],
    )

    res = client.get("/api/v1/customers/analytics/rfm?segment=New Lead")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_customers"] == 1
    assert data["customers"][0]["segment_label"] == "New Lead"
