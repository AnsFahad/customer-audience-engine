from fastapi.testclient import TestClient
from fastapi import status


def test_create_customer_success(client: TestClient):
    """Verifies that a valid customer registration returns 201 Created with full payload."""
    payload = {
        "email": "ananya.sharma@example.com",
        "first_name": "Ananya",
        "last_name": "Sharma",
        "country": "IN",
        "city": "Bengaluru",
        "consent_email": True,
        "consent_sms": False,
    }
    response = client.post("/api/v1/customers", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] is not None
    assert data["email"] == "ananya.sharma@example.com"
    assert data["first_name"] == "Ananya"
    assert data["country"] == "IN"
    assert data["consent_email"] is True
    assert data["consent_sms"] is False


def test_create_customer_duplicate_email(client: TestClient):
    """Verifies that registering a duplicate email returns 409 Conflict."""
    payload = {
        "email": "unique.user@example.com",
        "first_name": "Unique",
        "last_name": "User",
        "country": "US",
        "city": "Boston",
        "consent_email": True,
    }
    # First creation
    res1 = client.post("/api/v1/customers", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    # Duplicate attempt
    res2 = client.post("/api/v1/customers", json=payload)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in res2.json()["detail"]


def test_create_customer_validation_error(client: TestClient):
    """Verifies that invalid country code or bad email returns 422 Unprocessable Content."""
    # Bad country (not 2 chars)
    bad_country = {
        "email": "bad.country@example.com",
        "first_name": "Test",
        "last_name": "User",
        "country": "USA",  # Invalid! Must be 2 chars
    }
    res1 = client.post("/api/v1/customers", json=bad_country)
    assert res1.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Bad email
    bad_email = {
        "email": "not-an-email",
        "first_name": "Test",
        "last_name": "User",
        "country": "US",
    }
    res2 = client.post("/api/v1/customers", json=bad_email)
    assert res2.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_update_customer_empty_and_all_fields(client: TestClient):
    """Verifies updating all optional fields including empty patch, last_name, and consent_sms."""
    create_res = client.post(
        "/api/v1/customers",
        json={
            "email": "patch.all@example.com",
            "first_name": "First",
            "last_name": "Last",
            "country": "IN",
            "city": "Bengaluru",
            "consent_email": False,
            "consent_sms": False,
        },
    )
    cid = create_res.json()["id"]

    # 1. Empty patch payload returns unmodified customer
    res_empty = client.patch(f"/api/v1/customers/{cid}", json={})
    assert res_empty.status_code == status.HTTP_200_OK
    assert res_empty.json()["first_name"] == "First"

    # 2. Update last_name, consent_sms, city to null
    res_full = client.patch(
        f"/api/v1/customers/{cid}",
        json={
            "last_name": "UpdatedLast",
            "consent_sms": True,
            "city": None,
        },
    )
    assert res_full.status_code == status.HTTP_200_OK
    data = res_full.json()
    assert data["last_name"] == "UpdatedLast"
    assert data["consent_sms"] is True
    assert data["city"] is None

    # 3. Update non-existent customer returns 404
    res_missing = client.patch("/api/v1/customers/999999", json={"first_name": "Nobody"})
    assert res_missing.status_code == status.HTTP_404_NOT_FOUND


def test_get_customer_by_id(client: TestClient):
    """Verifies retrieving customer profile by ID returns 200 OK, and missing ID returns 404."""
    # Create
    create_res = client.post(
        "/api/v1/customers",
        json={
            "email": "lookup.test@example.com",
            "first_name": "Lookup",
            "last_name": "Test",
            "country": "IN",
            "consent_email": True,
        },
    )
    customer_id = create_res.json()["id"]

    # Get by ID
    get_res = client.get(f"/api/v1/customers/{customer_id}")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == customer_id
    assert get_res.json()["email"] == "lookup.test@example.com"

    # Get non-existent
    missing_res = client.get("/api/v1/customers/999999")
    assert missing_res.status_code == status.HTTP_404_NOT_FOUND


def test_update_customer_profile(client: TestClient):
    """Verifies updating customer profile details and consent flags returns 200 OK."""
    # Create
    create_res = client.post(
        "/api/v1/customers",
        json={
            "email": "update.test@example.com",
            "first_name": "Original",
            "last_name": "Name",
            "country": "IN",
            "city": "Mumbai",
            "consent_email": False,
        },
    )
    customer_id = create_res.json()["id"]

    # Update
    update_res = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={
            "first_name": "Modified",
            "city": "Pune",
            "consent_email": True,
        },
    )
    assert update_res.status_code == status.HTTP_200_OK
    updated = update_res.json()
    assert updated["first_name"] == "Modified"
    assert updated["city"] == "Pune"
    assert updated["consent_email"] is True
    # Unmodified fields persist
    assert updated["last_name"] == "Name"
    assert updated["email"] == "update.test@example.com"
