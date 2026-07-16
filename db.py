"""
SQLite persistence for the pizza ordering demo.

Two tables:
  customers — phone number is the identifier. If a shopper gives their
              phone number ("auth" in the loose demo sense — no password,
              just enough to recognize a returning customer), we can look
              up their last order and offer "the usual?" personalization.
  orders    — completed orders, linked to a customer when known, null
              customer_phone for guest checkouts.

This is intentionally simple — a real system would use a proper database
and real authentication. The point here is demonstrating the guest vs.
recognized-returning-customer flow, not building production auth.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get("PIZZA_DB_PATH", "pizza_orders.db")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                phone TEXT PRIMARY KEY,
                name TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_phone TEXT,
                items_json TEXT NOT NULL,
                total REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def upsert_customer(phone: str, name: Optional[str] = None):
    with _conn() as conn:
        existing = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            if name:
                conn.execute("UPDATE customers SET name = ? WHERE phone = ?", (name, phone))
        else:
            conn.execute("INSERT INTO customers (phone, name) VALUES (?, ?)", (phone, name))


def get_customer(phone: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def save_order(items: List[Dict[str, Any]], total: float, customer_phone: Optional[str] = None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (customer_phone, items_json, total) VALUES (?, ?, ?)",
            (customer_phone, json.dumps(items), total),
        )
        return cur.lastrowid


def get_last_order(customer_phone: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE customer_phone = ? ORDER BY id DESC LIMIT 1",
            (customer_phone,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["items"] = json.loads(result.pop("items_json"))
        return result


init_db()
