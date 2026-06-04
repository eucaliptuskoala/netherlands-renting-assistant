# storage.py — Database layer for Supabase PostgreSQL
# All functions for reading/writing listings in the database.
# Both main.py (scraper) and bot.py use this module.

import os  # To read SUPABASE_URL from environment
import sys  # To print errors to stderr
from datetime import datetime  # For timestamps in log messages

import psycopg2  # PostgreSQL database driver — lets Python talk to Supabase


# --- Helper: connect to Supabase ---
def _conn():
    """Create a new database connection. Returns None if SUPABASE_URL is not set."""
    url = os.environ.get("SUPABASE_URL")  # The full PostgreSQL connection string
    if not url:
        print(f"[{datetime.now():%H:%M:%S}] SUPABASE_URL not set", file=sys.stderr)
        return None
    return psycopg2.connect(url)  # Returns a connection object


# --- Load all seen listing IDs into a set (for fast duplicate checking) ---
def load_seen_ids():
    """Return a set of all listing_ids that already exist in the database."""
    conn = _conn()
    if not conn:
        return set()  # Return empty set so the scraper stores everything fresh
    try:
        with conn.cursor() as cur:
            # SELECT only the listing_id column, not the full rows — saves bandwidth
            cur.execute("select listing_id from seen_listings")
            # Fetch all rows and build a Python set (lookup is O(1) vs O(n) for lists)
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()  # Always close the connection, even if an error occurred


# --- Insert a new listing into the database ---
def mark_seen(listing_id, address=None, price=None, living_area=None, url=None):
    """Insert a new listing with status='new', or update it if it already exists. Returns True on success."""
    conn = _conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into seen_listings (listing_id, address, price, living_area, url, status, seen_at)
                values (%s, %s, %s, %s, %s, 'new', now())
                on conflict (listing_id) do update
                  set address = excluded.address,
                      price = excluded.price,
                      living_area = excluded.living_area,
                      url = excluded.url
                """,
                (listing_id, address, price, living_area, url),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] mark_seen failed: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()


# --- Get all listings with a given status ---
def get_listings_by_status(status):
    """Return a list of listing dicts filtered by status ('new', 'accepted', or 'rejected')."""
    conn = _conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            # Execute query with parameterized input — prevents SQL injection
            cur.execute(
                "select listing_id, address, price, living_area, url, status, seen_at from seen_listings where status = %s order by seen_at desc",
                (status,),
            )
            rows = cur.fetchall()
            # Convert each database row into a Python dictionary
            # Dictionaries are easier to work with in Python than raw tuples
            return [
                {
                    "listing_id": r[0],
                    "address": r[1],
                    "price": r[2],
                    "living_area": r[3],
                    "url": r[4],
                    "status": r[5],
                    "seen_at": r[6],
                }
                for r in rows
            ]
    finally:
        conn.close()


# --- Change a listing's status (e.g., from "new" to "accepted") ---
def update_status(listing_id, status):
    """Update the status column for a specific listing. Returns True on success."""
    conn = _conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update seen_listings set status = %s where listing_id = %s",
                (status, listing_id),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] update_status failed: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()
