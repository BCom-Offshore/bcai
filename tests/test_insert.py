#!/usr/bin/env python3
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
load_dotenv()

# Test direct insert
engine = create_engine("postgresql+psycopg://postgres:P%40ssw0rd@localhost:5432/bcai")
with engine.connect() as conn:
    # Delete any existing data
    conn.execute(text("DELETE FROM devices"))
    conn.execute(text("DELETE FROM links"))
    conn.execute(text("DELETE FROM sites"))
    conn.execute(text("DELETE FROM networks"))
    conn.execute(text("DELETE FROM customers"))
    conn.commit()
    
    # Insert test customer
    conn.execute(text("INSERT INTO customers (customer_id, customer_name) VALUES (999, 'Test Customer')"))
    conn.commit()
    
    # Verify
    result = conn.execute(text("SELECT COUNT(*) FROM customers"))
    print(f"Customers after insert: {result.scalar()}")
