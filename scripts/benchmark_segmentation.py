"""
Reproducible Benchmark Suite for Audience Segmentation Query.
Generates 5,000 synthetic customers and 50,000 events.
Measures execution time (median and p95) before and after composite indexes.
"""

import os
import sys
import time
import statistics
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

BENCHMARK_DB_FILE = "./benchmark_engine.db"
BENCHMARK_DB_URL = f"sqlite:///{BENCHMARK_DB_FILE}"

engine = create_engine(
    BENCHMARK_DB_URL,
    connect_args={"timeout": 60, "check_same_thread": False},
    poolclass=NullPool,
)


def setup_schema(conn):
    """Creates the base tables."""
    conn.execute(text("DROP TABLE IF EXISTS events;"))
    conn.execute(text("DROP TABLE IF EXISTS customers;"))

    conn.execute(text("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) NOT NULL UNIQUE,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            country VARCHAR(2) NOT NULL,
            city VARCHAR(100),
            consent_email BOOLEAN NOT NULL DEFAULT 0,
            consent_sms BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """))

    conn.execute(text("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key VARCHAR(100) NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            event_timestamp TIMESTAMP NOT NULL,
            monetary_value NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            event_payload JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
    """))
    conn.commit()


def seed_data(conn, num_customers=5000, num_events=50000):
    """Deterministically populates 5,000 customers and 50,000 events."""
    random.seed(42)
    now = datetime.now(timezone.utc)

    print(f"Generating {num_customers} synthetic customers...")
    cities = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Austin", "New York"]
    customer_params = []
    for i in range(1, num_customers + 1):
        city = cities[i % len(cities)]
        consent = (i % 4 != 0)  # 75% consent = True
        created = (now - timedelta(days=random.randint(30, 180))).isoformat()
        customer_params.append((
            f"user_{i}@benchmark.test",
            f"First{i}",
            f"Last{i}",
            "IN" if i % 6 != 0 else "US",
            city,
            1 if consent else 0,
            1 if consent else 0,
            created,
            created,
        ))

    cursor = conn.connection.cursor()
    cursor.executemany(
        """
        INSERT INTO customers (email, first_name, last_name, country, city, consent_email, consent_sms, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customer_params,
    )
    conn.commit()

    print(f"Generating {num_events} synthetic behavioral events...")
    categories = ["Electronics", "Fashion", "Home", "Books"]
    event_types = ["VIEW_PRODUCT", "VIEW_PRODUCT", "ADD_TO_CART", "PURCHASE"]

    event_params = []
    for i in range(1, num_events + 1):
        cid = random.randint(1, num_customers)
        cat = categories[i % len(categories)]
        etype = event_types[i % len(event_types)]
        val = 0.0 if etype != "PURCHASE" else round(random.uniform(20.0, 400.0), 2)
        ts = (now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))).isoformat()
        payload = f'{{"category": "{cat}", "sku": "SKU-{i % 500}"}}'
        event_params.append((
            f"evt_bench_{i}",
            cid,
            etype,
            ts,
            val,
            payload,
            ts,
        ))

        # Batch commit every 10,000
        if len(event_params) >= 10000:
            cursor.executemany(
                """
                INSERT INTO events (event_key, customer_id, event_type, event_timestamp, monetary_value, event_payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                event_params,
            )
            conn.commit()
            event_params = []

    if event_params:
        cursor.executemany(
            """
            INSERT INTO events (event_key, customer_id, event_type, event_timestamp, monetary_value, event_payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            event_params,
        )
        conn.commit()

    print("Data generation complete.")


SEGMENTATION_SQL = """
SELECT 
    c.id,
    c.email,
    c.first_name,
    c.city,
    c.country
FROM customers c
WHERE 
    LOWER(c.city) = 'bengaluru'
    AND c.consent_email = 1
    AND EXISTS (
        SELECT 1 
        FROM events e 
        WHERE e.customer_id = c.id
          AND e.event_type IN ('VIEW_PRODUCT', 'ADD_TO_CART')
          AND e.event_timestamp >= datetime('now', '-30 days')
          AND json_extract(e.event_payload, '$.category') = 'Electronics'
    )
    AND NOT EXISTS (
        SELECT 1 
        FROM events pe 
        WHERE pe.customer_id = c.id
          AND pe.event_type = 'PURCHASE'
          AND pe.event_timestamp >= datetime('now', '-14 days')
          AND json_extract(pe.event_payload, '$.category') = 'Electronics'
    )
ORDER BY c.id
LIMIT 20;
"""


def benchmark_query(conn, repetitions=50):
    """Executes query N times and returns timing stats in milliseconds."""
    durations = []
    # Warmup
    conn.execute(text(SEGMENTATION_SQL)).fetchall()

    for _ in range(repetitions):
        start = time.perf_counter()
        rows = conn.execute(text(SEGMENTATION_SQL)).fetchall()
        end = time.perf_counter()
        durations.append((end - start) * 1000.0)

    durations.sort()
    median_time = statistics.median(durations)
    p95_time = durations[int(len(durations) * 0.95)]
    min_time = min(durations)
    max_time = max(durations)

    return {
        "repetitions": repetitions,
        "median_ms": round(median_time, 2),
        "p95_ms": round(p95_time, 2),
        "min_ms": round(min_time, 2),
        "max_ms": round(max_time, 2),
        "sample_count": len(rows),
    }


def get_query_plan(conn):
    """Retrieves EXPLAIN QUERY PLAN."""
    plan_rows = conn.execute(text(f"EXPLAIN QUERY PLAN {SEGMENTATION_SQL}")).fetchall()
    return [str(row) for row in plan_rows]


def run_benchmark():
    with engine.connect() as conn:
        setup_schema(conn)
        seed_data(conn, num_customers=5000, num_events=50000)

        # ------------------- SCENARIO 1: WITHOUT INDEXES -------------------
        print("\n" + "=" * 60)
        print("SCENARIO 1: WITHOUT INDEXES (BASELINE)")
        print("=" * 60)
        plan_no_index = get_query_plan(conn)
        print("Query Plan (No Indexes):")
        for line in plan_no_index:
            print("  ", line)

        stats_no_index = benchmark_query(conn, repetitions=30)
        print(f"Timing over {stats_no_index['repetitions']} runs:")
        print(f"  Median: {stats_no_index['median_ms']} ms")
        print(f"  p95:    {stats_no_index['p95_ms']} ms")
        print(f"  Min:    {stats_no_index['min_ms']} ms | Max: {stats_no_index['max_ms']} ms")

        # ------------------- SCENARIO 2: WITH COMPOSITE INDEXES -------------------
        print("\n" + "=" * 60)
        print("SCENARIO 2: WITH COMPOSITE B-TREE INDEXES")
        print("=" * 60)
        print("Creating indexes: ix_events_customer_type_time, ix_customers_consent_city...")
        conn.execute(text("CREATE INDEX ix_events_customer_type_time ON events (customer_id, event_type, event_timestamp);"))
        conn.execute(text("CREATE INDEX ix_customers_consent_city ON customers (consent_email, city);"))
        conn.commit()

        plan_indexed = get_query_plan(conn)
        print("Query Plan (With Indexes):")
        for line in plan_indexed:
            print("  ", line)

        stats_indexed = benchmark_query(conn, repetitions=30)
        print(f"Timing over {stats_indexed['repetitions']} runs:")
        print(f"  Median: {stats_indexed['median_ms']} ms")
        print(f"  p95:    {stats_indexed['p95_ms']} ms")
        print(f"  Min:    {stats_indexed['min_ms']} ms | Max: {stats_indexed['max_ms']} ms")

        # Speedup calculation
        speedup = round(stats_no_index['median_ms'] / stats_indexed['median_ms'], 2)
        print("\n" + "=" * 60)
        print(f"PERFORMANCE GAIN: {speedup}x FASTER WITH COMPOSITE INDEXES")
        print(f"Median: {stats_no_index['median_ms']} ms -> {stats_indexed['median_ms']} ms")
        print(f"p95:    {stats_no_index['p95_ms']} ms -> {stats_indexed['p95_ms']} ms")
        print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
