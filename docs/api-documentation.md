# REST API Specification & Data Contracts

## 1. Overview & Conventions

All endpoints follow RESTful standards and are prefixed with `/api/v1`.
- **Payload Format:** JSON (`Content-Type: application/json`)
- **Timestamps:** ISO 8601 with timezone (e.g. `2026-11-18T10:30:00Z`)
- **HTTP Status Codes:**
  - `200 OK`: Successful read or idempotent update
  - `201 Created`: Resource successfully created
  - `400 Bad Request`: Business rule violation
  - `404 Not Found`: Resource does not exist
  - `409 Conflict`: Unique constraint violation (e.g. duplicate email)
  - `422 Unprocessable Entity`: Pydantic schema validation failure
  - `503 Service Unavailable`: Database or critical dependency offline

---

## 2. Customer Profile Endpoints

### `POST /api/v1/customers`
Registers a new customer profile with marketing consent preferences.

- **Request Body:**
```json
{
  "email": "rahul.verma@example.com",
  "first_name": "Rahul",
  "last_name": "Verma",
  "country": "IN",
  "city": "Bengaluru",
  "consent_email": true,
  "consent_sms": false
}
```

- **Response (201 Created):**
```json
{
  "id": 101,
  "email": "rahul.verma@example.com",
  "first_name": "Rahul",
  "last_name": "Verma",
  "country": "IN",
  "city": "Bengaluru",
  "consent_email": true,
  "consent_sms": false,
  "created_at": "2026-11-18T10:30:00Z",
  "updated_at": "2026-11-18T10:30:00Z"
}
```

---

### `GET /api/v1/customers/{customer_id}`
Retrieves customer profile by ID.

- **Response (200 OK):**
```json
{
  "id": 101,
  "email": "rahul.verma@example.com",
  "first_name": "Rahul",
  "last_name": "Verma",
  "country": "IN",
  "city": "Bengaluru",
  "consent_email": true,
  "consent_sms": false,
  "created_at": "2026-11-18T10:30:00Z",
  "updated_at": "2026-11-18T10:30:00Z"
}
```

---

### `PATCH /api/v1/customers/{customer_id}`
Updates customer profile details and consent flags.

- **Request Body:**
```json
{
  "city": "Pune",
  "consent_email": false
}
```

- **Response (200 OK):**
```json
{
  "id": 101,
  "email": "rahul.verma@example.com",
  "first_name": "Rahul",
  "last_name": "Verma",
  "country": "IN",
  "city": "Pune",
  "consent_email": false,
  "consent_sms": false,
  "created_at": "2026-11-18T10:30:00Z",
  "updated_at": "2026-11-18T11:45:00Z"
}
```

---

## 3. Behavioral Event Endpoints

### `POST /api/v1/events`
Logs a discrete customer behavioral action (`VIEW_PRODUCT`, `ADD_TO_CART`, `PURCHASE`).
Supports idempotent ingestion via `event_key`.

- **Request Body:**
```json
{
  "event_key": "evt_purchase_9821",
  "customer_id": 101,
  "event_type": "PURCHASE",
  "event_timestamp": "2026-11-18T11:15:00Z",
  "monetary_value": 175.50,
  "event_payload": {
    "order_id": "ORD-9821",
    "category": "Electronics",
    "item_count": 2,
    "device": "mobile"
  }
}
```

- **Response (201 Created for new, 200 OK for idempotent duplicate):**
```json
{
  "id": 5001,
  "event_key": "evt_purchase_9821",
  "customer_id": 101,
  "event_type": "PURCHASE",
  "event_timestamp": "2026-11-18T11:15:00Z",
  "monetary_value": 175.50,
  "event_payload": {
    "order_id": "ORD-9821",
    "category": "Electronics",
    "item_count": 2,
    "device": "mobile"
  },
  "created_at": "2026-11-18T11:15:02Z"
}
```

- **Conflict Response (409 Conflict):**
Returned when an existing `event_key` is reused with a different payload.
```json
{
  "detail": "Idempotency conflict: event_key 'evt_purchase_9821' was previously ingested with a different payload."
}
```

---

### `GET /api/v1/customers/{customer_id}/events?limit=100&offset=0`
Fetches behavioral interactions for a specific customer in reverse chronological order.

- **Response (200 OK):**
```json
[
  {
    "id": 5001,
    "event_key": "evt_purchase_9821",
    "customer_id": 101,
    "event_type": "PURCHASE",
    "event_timestamp": "2026-11-18T11:15:00Z",
    "monetary_value": 175.50,
    "event_payload": {
      "order_id": "ORD-9821",
      "category": "Electronics"
    },
    "created_at": "2026-11-18T11:15:02Z"
  }
]
```

---

## 4. Audience Segmentation Endpoints

### `POST /api/v1/segments/preview`
Evaluates multi-condition dynamic audience rules using database-level `EXISTS` and `NOT EXISTS` subqueries.

- **Request Body:**
```json
{
  "city": "Bengaluru",
  "product_category": "Electronics",
  "activity_days": 30,
  "exclude_purchase_days": 14,
  "require_marketing_consent": true
}
```

- **Response (200 OK):**
```json
{
  "matching_count": 1420,
  "sample_customers": [
    {
      "id": 101,
      "email": "rahul.verma@example.com",
      "first_name": "Rahul",
      "last_name": "Verma",
      "city": "Bengaluru",
      "country": "IN",
      "consent_email": true
    }
  ],
  "applied_filters": {
    "city": "Bengaluru",
    "product_category": "Electronics",
    "activity_days": 30,
    "exclude_purchase_days": 14,
    "require_marketing_consent": true
  }
}
```

---

## 5. Campaign Management Endpoints

### `POST /api/v1/campaigns`
Creates a marketing campaign and atomically materializes its qualified audience into `campaign_audience` inside a single ACID database transaction.

- **Request Body:**
```json
{
  "name": "Diwali VIP Electronics Shoppers",
  "description": "High-value shoppers in Bengaluru who viewed Electronics recently",
  "segment_rules": {
    "city": "Bengaluru",
    "product_category": "Electronics",
    "activity_days": 30,
    "exclude_purchase_days": 14,
    "require_marketing_consent": true
  }
}
```

- **Response (201 Created):**
```json
{
  "id": 5,
  "name": "Diwali VIP Electronics Shoppers",
  "description": "High-value shoppers in Bengaluru who viewed Electronics recently",
  "status": "active",
  "segment_rules": {
    "city": "Bengaluru",
    "product_category": "Electronics",
    "activity_days": 30,
    "exclude_purchase_days": 14,
    "require_marketing_consent": true
  },
  "audience_count": 1420,
  "created_at": "2026-11-18T11:30:00Z",
  "updated_at": "2026-11-18T11:30:00Z"
}
```

---

### `GET /api/v1/campaigns/{campaign_id}/audience?limit=50&offset=0`
Retrieves paginated materialized audience members for an active campaign.

- **Response (200 OK):**
```json
{
  "campaign_id": 5,
  "campaign_name": "Diwali VIP Electronics Shoppers",
  "total_audience_count": 1420,
  "limit": 50,
  "offset": 0,
  "members": [
    {
      "customer_id": 101,
      "email": "rahul.verma@example.com",
      "first_name": "Rahul",
      "last_name": "Verma",
      "city": "Bengaluru",
      "country": "IN",
      "matched_at": "2026-11-18T11:35:00Z",
      "status": "qualified"
    }
  ]
}
```

### `POST /api/v1/campaigns`
Creates a marketing campaign with dynamic audience targeting rules.

- **Request Body:**
```json
{
  "name": "Diwali VIP Electronics Shoppers",
  "description": "High-value shoppers in India who purchased electronics recently",
  "segment_rules": {
    "country": "IN",
    "channel": "email",
    "event_filters": {
      "event_type": "purchase",
      "min_total_spend": 150.00,
      "days_window": 30
    }
  }
}
```

- **Response (201 Created):**
```json
{
  "id": 5,
  "name": "Diwali VIP Electronics Shoppers",
  "description": "High-value shoppers in India who purchased electronics recently",
  "status": "draft",
  "segment_rules": {
    "country": "IN",
    "channel": "email",
    "event_filters": {
      "event_type": "purchase",
      "min_total_spend": 150.00,
      "days_window": 30
    }
  },
  "created_at": "2026-11-18T11:30:00Z",
  "updated_at": "2026-11-18T11:30:00Z"
}
```

---

### `POST /api/v1/campaigns/{id}/evaluate`
Triggers the segmentation engine to query matching customers and materialize the audience into `campaign_audience`.

- **Response (200 OK):**
```json
{
  "campaign_id": 5,
  "status": "completed",
  "qualified_count": 1420,
  "evaluated_at": "2026-11-18T11:35:00Z"
}
```

---

### `GET /api/v1/campaigns/{id}/audience?limit=50&offset=0`
Fetches paginated members of the campaign audience.

- **Response (200 OK):**
```json
{
  "campaign_id": 5,
  "total_count": 1420,
  "limit": 50,
  "offset": 0,
  "customers": [
    {
      "customer_id": 101,
      "email": "rahul.verma@example.com",
      "first_name": "Rahul",
      "matched_at": "2026-11-18T11:35:00Z",
      "status": "qualified"
    }
  ]
}
```
