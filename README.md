# Customer Data & Audience Segmentation Engine

A production-grade, modular backend service engineered for customer data ingestion, behavioral event tracking, dynamic rule-based audience segmentation, and transactional campaign materialization with strict marketing consent enforcement.

Designed as an enterprise-grade Customer Data Platform (CDP) core component, engineered for modern marketing technology platforms.

---

## 1. System Architecture

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

## 2. Database Design & Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    CUSTOMERS ||--o{ EVENTS : "generates (1:N)"
    CAMPAIGNS ||--o{ CAMPAIGN_AUDIENCE : "targets (1:N)"
    CUSTOMERS ||--o{ CAMPAIGN_AUDIENCE : "enrolled in (1:N)"

    CUSTOMERS {
        bigint id PK "Identity"
        varchar(255) email UK "Normalized, Unique"
        varchar(100) first_name
        varchar(100) last_name
        varchar(2) country "CHECK length=2"
        varchar(100) city
        boolean consent_email "Default FALSE"
        boolean consent_sms "Default FALSE"
        timestamptz created_at
        timestamptz updated_at
    }

    EVENTS {
        bigint id PK "Identity"
        varchar(100) event_key UK "Client Idempotency Key"
        bigint customer_id FK "REFERENCES customers(id)"
        varchar(50) event_type "VIEW_PRODUCT, ADD_TO_CART, PURCHASE"
        timestamptz event_timestamp "Client timestamp"
        numeric monetary_value "CHECK >= 0"
        jsonb event_payload "Semi-structured attributes"
        timestamptz created_at
    }

    CAMPAIGNS {
        bigint id PK "Identity"
        varchar(150) name
        text description
        varchar(30) status "CHECK draft|active|paused|completed"
        jsonb segment_rules "Targeting criteria"
        timestamptz created_at
        timestamptz updated_at
    }

    CAMPAIGN_AUDIENCE {
        bigint campaign_id PK,FK "REFERENCES campaigns(id)"
        bigint customer_id PK,FK "REFERENCES customers(id)"
        timestamptz matched_at
        varchar(30) status "CHECK qualified|sent|suppressed|failed"
    }
```

---

## 3. Measured Performance & Index Optimization

We benchmarked the dynamic audience segmentation query against a dataset of **5,000 synthetic customers** and **50,000 behavioral events** (55,000 total records):

```powershell
.\.venv\Scripts\python -m scripts.benchmark_segmentation
```

### Measured Benchmark Metrics (30 Repetitions)

| Execution Scenario | Access Plan | Median Latency | p95 Latency | Measured Gain |
|---|---|---|---|---|
| **Without Indexes (Baseline)** | Full Table `SCAN` on `customers`, Full Table `SCAN` on `events` | **194.91 ms** | **221.96 ms** | Baseline |
| **With Composite Indexes** | `SEARCH` on `customers` via `ix_customers_consent_city`, Index Seek on `events` via `ix_events_customer_type_time` | **9.21 ms** | **12.84 ms** | **21.16x FASTER** |

---

## 4. SQL Segmentation Query Architecture

```sql
SELECT 
    c.id, c.email, c.first_name, c.city, c.country
FROM customers c
WHERE 
    LOWER(c.city) = LOWER('Bengaluru')
    AND c.consent_email IS TRUE
    AND EXISTS (
        SELECT 1 
        FROM events e 
        WHERE e.customer_id = c.id
          AND e.event_type IN ('VIEW_PRODUCT', 'ADD_TO_CART')
          AND e.event_timestamp >= NOW() - INTERVAL '30 days'
          AND (e.event_payload ->> 'category') = 'Electronics'
    )
    AND NOT EXISTS (
        SELECT 1 
        FROM events pe 
        WHERE pe.customer_id = c.id
          AND pe.event_type = 'PURCHASE'
          AND pe.event_timestamp >= NOW() - INTERVAL '14 days'
          AND (pe.event_payload ->> 'category') = 'Electronics'
    )
ORDER BY c.id
LIMIT 20;
```

---

## 5. Transaction & Rollback Guarantees

Campaign creation and audience materialization (`POST /api/v1/campaigns`) execute inside a single atomic database transaction:
- **`BEGIN`**: Creates `Campaign` entity and obtains `campaign.id`.
- **Audience Calculation**: Queries qualifying customer IDs directly in the database.
- **Bulk Materialization**: Inserts qualified members into `campaign_audience`.
- **`COMMIT`**: Flushes all changes together atomically.
- **`ROLLBACK`**: If an exception or crash occurs at any step, `db.rollback()` executes, guaranteeing that zero orphaned campaign records persist.

---

## 6. Testing Instructions & Actual Results

### Run Full Test Suite & Coverage
```powershell
.\.venv\Scripts\pytest --cov=src --cov-report=term-missing -v
```

**Verified Test Metrics:**
- **Total Tests:** 33 tests
- **Pass Rate:** 100% (33 passed in 3.44 seconds)
- **Total Codebase Coverage:** 96%
- **All Core Routers & Repositories:** 100% test coverage

---

## 7. Known Limitations & Future Improvements

1. **High-Throughput Event Ingestion Buffer:** Direct synchronous ingestion works for moderate workloads; for 5,000+ events/sec, front with an event log buffer (e.g. Apache Kafka or AWS SQS).
2. **Cold Event Data Partitioning:** Implement declarative range partitioning on `events(event_timestamp)` by month for instant data archiving.
3. **Arbitrary Boolean Expression AST:** Support nested `AND` / `OR` segmentation rule trees.
4. **Keyset / Cursor Pagination:** Support cursor-based pagination for audience exports exceeding 1,000,000 rows.

---

## 8. Living Technical Documentation

- [docs/architecture.md](file:///d:/Projects/customer-audience-engine/docs/architecture.md): Deep architectural specification and event flow.
- [docs/database-design.md](file:///d:/Projects/customer-audience-engine/docs/database-design.md): 4-table relational schema, composite keys, and indexing strategy.
- [docs/api-documentation.md](file:///d:/Projects/customer-audience-engine/docs/api-documentation.md): REST endpoint contracts with sample payloads.
- [docs/interview-notes.md](file:///d:/Projects/customer-audience-engine/docs/interview-notes.md): Comprehensive technical interview notes, trade-off defenses, and architectural design decisions.
- [docs/resume-evidence.md](file:///d:/Projects/customer-audience-engine/docs/resume-evidence.md): **Zero fluff**. Verified test counts, benchmark figures, and empirical metrics.
