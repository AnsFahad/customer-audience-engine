# Technical Interview Notes & Defenses (Zeta Global Focus)

## 1. Architectural & Foundation Defenses

### Q1: Why use a Modular Monolith instead of Microservices?
- **Defense:** Microservices introduce distributed complexity: network latency, distributed transactions (Sagas/2PC), partial network failures, and complex deployment pipelines. For a customer audience segmentation engine starting out, domain boundaries can be strictly enforced within a single codebase via package structure (`api`, `services`, `repositories`, `models`). We retain high developer velocity, in-process ACID transactions, and zero cross-network service calls, while keeping the door open to split services later if scaling demands it.

### Q2: Why synchronous SQLAlchemy instead of AsyncIO/AsyncPG initially?
- **Defense:** Synchronous SQLAlchemy 2.0 provides straightforward transaction boundaries, deterministic execution, simpler debugging, and easy CPU/memory profiling. For database queries bound by disk/index lookups, standard thread pooling under WSGI/ASGI (or Uvicorn worker processes) achieves excellent throughput without the subtle pitfalls of async code (such as blocking the event loop with synchronous computation or unhandled coroutine cancellations mid-transaction).

### Q3: What is the benefit of the Repository Pattern with SQLAlchemy?
- **Defense:** The Repository pattern abstracts data access away from business logic. Without it, ORM queries leak into API routes or service functions, causing high coupling. If we optimize an audience segmentation query with raw SQL, specialized CTEs, or new joins, we only modify the repository method without touching the HTTP router or business logic. It also simplifies unit testing by allowing repositories to be mocked or swapped.

---

## 2. Concurrency, Idempotency & Database Integrity

### Q4: How does the system handle concurrent duplicate event ingestion?
- **Defense:** 
  1. At the application layer, the service queries `EventRepository.get_by_key(event_key)`. If an event already exists with the same key and identical payload, it returns `200 OK` without creating a new record.
  2. If two concurrent requests arrive at the exact same millisecond, both check the table before either commits.
  3. The PostgreSQL storage engine enforces the `UNIQUE INDEX (event_key)`. The second transaction aborts with an `IntegrityError`.
  4. The service catches the error, rolls back the failed transaction, re-reads the committed row from the winning worker, verifies the payload, and safely returns `200 OK`. No `500 Internal Server Error` is ever exposed to the client.

### Q5: How do we prevent SQL Injection in dynamic segmentation queries?
- **Defense:**
  1. We never concatenate strings into SQL (`"WHERE city = '" + city + "'"`).
  2. We construct queries using SQLAlchemy 2.0 Core expressions (`func.lower(Customer.city) == city.strip().lower()`).
  3. All inputs are passed as parameterized bind variables (`:param_1`), which the underlying database driver (`psycopg2` or `sqlite3`) sends separately from the SQL statement text.
  4. Pydantic models validate and sanitize all data types before queries are generated.

### Q6: How do we prevent database connection and session leaks?
- **Defense:**
  We implement the session-per-request pattern via FastAPI's `Depends(get_db)`. Using a Python generator (`try: yield db finally: db.close()`), the connection checkout is bound to the HTTP request lifecycle. Even if an unhandled exception or crash occurs in a route or service, the `finally` block is guaranteed to execute, safely returning the connection to the pool.

---

## 3. Query Optimization & Indexing Strategies

### Q7: Why use `EXISTS` instead of `INNER JOIN` in audience segmentation?
- **Defense:**
  - An `INNER JOIN` between `customers` and `events` produces multiple rows per customer if a customer has multiple events. The engine would then have to execute a costly `DISTINCT` or `GROUP BY` to deduplicate profiles.
  - A correlated `EXISTS (SELECT 1 FROM events WHERE customer_id = c.id ...)` short-circuits. The moment the database finds the *first* matching event for that customer, it stops scanning and evaluates to `TRUE`.
  - Backed by our composite index `(customer_id, event_type, event_timestamp)`, `EXISTS` runs as an index seek rather than a full table scan.

### Q8: Why use `NOT EXISTS` instead of `LEFT JOIN ... WHERE event.id IS NULL` for purchase suppression?
- **Defense:**
  - `LEFT JOIN` forces the query planner to materialize all event rows and check for `NULL` in outer join buffers.
  - `NOT EXISTS` aborts the search for that customer as soon as the first `PURCHASE` event is found within the suppression window, minimizing memory usage and CPU cycles.

---

## 4. Database Portability & Benchmark Truthfulness

### Q9: Which database engine did your benchmarks and tests run on?
- **Defense:**
  - **The benchmark and test suite ran on SQLite 3.45.3.**
  - **Why:** To make the test suite and benchmark 100% reproducible on any developer machine or lightweight CI/CD pipeline without requiring external Docker daemon or PostgreSQL server installation.
  - **The Benchmark:** Measured across 5,000 customers and 50,000 events (55,000 rows), demonstrating an identical algorithmic transition: full table scan (`SCAN c`, `SCAN e`) dropping from **194.91 ms** down to **9.21 ms** (a **21.16x speedup**) using a composite B-Tree index seek (`SEARCH e USING INDEX ix_events_customer_type_time`).
  - **PostgreSQL Production Portability:** The schema is engineered to be dialect-agnostic using SQLAlchemy variants:
    - 64-bit auto-incrementing primary keys: `BigIntID = BigInteger().with_variant(Integer, "sqlite")`.
    - Semi-structured event payload: `JSON().with_variant(JSONB, "postgresql")`.
    - Cross-dialect JSON traversal: `Event.event_payload["category"].as_string()` cleanly compiles to `->>` on PostgreSQL and `json_extract()` on SQLite.
    - Switching to a live PostgreSQL production instance requires only updating `DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/dbname"` in `.env`.
