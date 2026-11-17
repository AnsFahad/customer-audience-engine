"""Verification script running raw SQL queries across all four tables."""

from sqlalchemy import text
from src.core.database import engine


def verify():
    with engine.connect() as conn:
        print("================ TABLE RECORD COUNTS ================")
        for table in ["customers", "events", "campaigns", "campaign_audience"]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"{table}: {count} records")

        print("\n================ RAHUL VERMA RECORD ================")
        rahul = conn.execute(
            text(
                "SELECT id, email, first_name, country, consent_email "
                "FROM customers WHERE email = :email"
            ),
            {"email": "rahul.verma@example.com"},
        ).mappings().first()
        print("Customer:", dict(rahul))

        events = conn.execute(
            text(
                "SELECT event_type, monetary_value, event_timestamp "
                "FROM events WHERE customer_id = :cid ORDER BY event_timestamp"
            ),
            {"cid": rahul["id"]},
        ).mappings().all()
        print("Events for Rahul:")
        for e in events:
            print("  -", dict(e))

        print("\n================ SQL AUDIENCE EVALUATION ================")
        # Tests audience qualification logic: IN customers with consent_email=True and spend >= 150
        audience_query = text("""
            SELECT 
                c.id AS customer_id,
                c.email,
                c.first_name,
                c.country,
                c.consent_email,
                SUM(e.monetary_value) AS total_spend,
                COUNT(e.id) AS purchase_count
            FROM customers c
            INNER JOIN events e ON c.id = e.customer_id
            WHERE 
                c.country = 'IN'
                AND c.consent_email = 1
                AND e.event_type = 'purchase'
            GROUP BY c.id, c.email, c.first_name, c.country, c.consent_email
            HAVING SUM(e.monetary_value) >= 150.00
        """)
        qualified = conn.execute(audience_query).mappings().all()
        print("Customers matching 'Diwali VIP Electronics' criteria:")
        for q in qualified:
            print("  Qualified:", dict(q))

        print("\n================ CAMPAIGN AUDIENCE MEMBERSHIPS ================")
        ca = conn.execute(text("""
            SELECT ca.campaign_id, c.email, ca.status, ca.matched_at 
            FROM campaign_audience ca 
            JOIN customers c ON ca.customer_id = c.id
            ORDER BY ca.campaign_id, c.id
        """)).mappings().all()
        for row in ca:
            print("  Member:", dict(row))


if __name__ == "__main__":
    verify()
