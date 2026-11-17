# System Architecture & Technical Design Specification

## 1. System Overview

The **Customer Data & Audience Segmentation Engine** is a high-performance, modular Customer Data Platform (CDP) core service designed for enterprise marketing technology platforms.

It ingests customer profiles and behavioral interaction streams, evaluates multi-condition audience segmentation criteria across demographic and behavioral attributes, enforces strict consumer marketing consent (GDPR/CCPA/CAN-SPAM), and computes campaign-ready audience cohorts.

---

## 2. Core Architectural Patterns

The engine adheres to a **Modular Monolith** architecture with strict layer decoupling and single-direction dependency flow:

```
[ Ingestion API / Campaign Manager ]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ Presentation Layer (src/api)                           │
│ - FastAPI Routers & HTTP Request Validation            │
│ - Pydantic Request/Response DTOs                       │
│ - Dependency Injection for DB Sessions & Services      │
└──────────────────────────┬─────────────────────────────┘
                           │ Validated DTOs
                           ▼
┌────────────────────────────────────────────────────────┐
│ Domain & Service Layer (src/services)                  │
│ - Audience Rule Engine & SQL Translation               │
│ - Mandatory Marketing Consent Enforcement              │
│ - Campaign Membership Orchestration                    │
│ - Business Invariants & Transaction Boundaries         │
└──────────────────────────┬─────────────────────────────┘
                           │ Domain Entities & Query Criteria
                           ▼
┌────────────────────────────────────────────────────────┐
│ Data Access & Repository Layer (src/repositories)      │
│ - SQLAlchemy 2.0 Query Construction                    │
│ - Dynamic Predicate Building & Aggregation Queries     │
│ - Batch Ingestion & Keyset/Offset Pagination           │
│ - Index Optimization & Query Execution                 │
└──────────────────────────┬─────────────────────────────┘
                           │ SQLAlchemy Session / Units of Work
                           ▼
┌────────────────────────────────────────────────────────┐
│ Persistence Layer (PostgreSQL / Relational Engine)     │
│ - 4 Relational Tables (ACID Guarantee)                 │
│ - Foreign Key Integrity & Check Constraints            │
│ - Composite & B-Tree Indexes                           │
└────────────────────────────────────────────────────────┘
```

---

## 3. How Customer Events Flow Through the Backend

When a customer performs an action on an e-commerce platform or mobile app (e.g. viewing a product, adding to cart, completing a purchase), the event traverses the backend via the following pipeline:

```
1. Client Event Payload (HTTP POST /api/v1/events)
   │
   ▼
2. Presentation Layer (src/api/v1/events.py)
   - Deserializes JSON payload into `EventCreate` Pydantic schema.
   - Validates schema types: ISO-8601 timestamp, non-negative monetary_value, allowed event_types.
   │
   ▼
3. Service Layer (src/services/event_service.py)
   - Idempotency Check: Verifies whether `event_key` has already been ingested.
   - If identical payload: returns existing event with HTTP 200 OK.
   - If conflicting payload: raises HTTP 409 Conflict.
   - Customer Validation: Verifies customer_id exists in database (or raises 404).
   - Validates event timestamp (rejects future-dated events).
   │
   ▼
4. Repository Layer (src/repositories/event_repository.py)
   - Constructs SQLAlchemy 2.0 `insert(Event)` statement.
   - Attaches event to the request-scoped database session.
   │
   ▼
5. Persistence Layer (PostgreSQL `events` table)
   - Writes event record inside a transaction.
   - Updates table indexes: `(customer_id, event_type, event_timestamp)` and `(event_key)`.
   - On commit, event becomes immediately queryable for audience segmentation.
```

---

## 4. Transaction Boundaries & Atomicity

A database transaction (`BEGIN ... COMMIT / ROLLBACK`) guarantees the **ACID** properties (Atomicity, Consistency, Isolation, Durability). In this engine, transactions are strictly required at the following critical boundaries:

1. **Campaign Creation & Audience Materialization (`POST /api/v1/campaigns`)**:
   - The campaign record and its materialized audience members are written inside a single atomic transaction.
   ```sql
   BEGIN;
   -- Step 1: Create Campaign entity
   INSERT INTO campaigns (name, description, status, segment_rules, created_at, updated_at)
   VALUES ('Diwali VIP Sale', '...', 'active', '{...}', NOW(), NOW()) RETURNING id;

   -- Step 2: Query and insert qualified audience members
   INSERT INTO campaign_audience (campaign_id, customer_id, matched_at, status)
   SELECT :campaign_id, c.id, NOW(), 'qualified'
   FROM customers c
   WHERE c.consent_email = TRUE AND ...;

   COMMIT; -- Commits BOTH together
   ```
   - **Rollback Guarantee:** If an exception occurs during audience evaluation or insertion, `db.rollback()` executes, guaranteeing that zero orphaned campaign rows persist.

2. **Customer Consent Revocation (GDPR / CCPA Opt-Out)**:
   - When a customer opts out of email marketing (`consent_email = FALSE`), the system updates `customers.consent_email = FALSE` AND updates or purges that customer from all active campaigns in `campaign_audience` atomically.

---

## 5. Known Limitations & Future Improvements

1. **Scale-Out Ingestion (Message Queues):**
   - *Current Design:* Direct synchronous HTTP ingestion into PostgreSQL with `UNIQUE(event_key)` idempotency.
   - *Future Enhancement:* When event ingestion exceeds 5,000 requests/second, introduce Apache Kafka or AWS SQS in front of worker pools to absorb traffic spikes and buffer writes.
2. **Cold Data Partitioning:**
   - *Current Design:* Single `events` table backed by composite B-Tree indexes.
   - *Future Enhancement:* Use PostgreSQL declarative table partitioning by range (`PARTITION BY RANGE (event_timestamp)`) with monthly partitions to drop old event logs instantly without vacuum overhead.
3. **Complex Segment Rule Trees (Boolean AST):**
   - *Current Design:* Multi-clause segmentation supporting city, category, activity days, purchase suppression, and consent.
   - *Future Enhancement:* A nested Abstract Syntax Tree (AST) supporting arbitrary combinations of `AND` / `OR` condition groups serialized as JSON.
4. **Asynchronous Keyset Pagination:**
   - *Current Design:* Standard offset/limit pagination for audience export.
   - *Future Enhancement:* Keyset / cursor-based pagination using `(matched_at, customer_id)` to ensure $O(1)$ page traversal for audiences exceeding 1,000,000 members.
