import os
import sys
from datetime import datetime

import psycopg2


def _conn():
    url = os.environ.get('SUPABASE_URL')
    if not url:
        print(f"[{datetime.now():%H:%M:%S}] SUPABASE_URL not set", file=sys.stderr)
        return None
    return psycopg2.connect(url)


def load_seen_ids():
    conn = _conn()
    if not conn:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute('select listing_id from seen_listings')
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def mark_seen(listing_id, address=None, price=None, living_area=None, url=None):
    conn = _conn()
    if not conn:
        return
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
    finally:
        conn.close()


def get_listings_by_status(status):
    conn = _conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                'select listing_id, address, price, living_area, url, status, seen_at from seen_listings where status = %s order by seen_at desc',
                (status,),
            )
            rows = cur.fetchall()
            return [
                {
                    'listing_id': r[0],
                    'address': r[1],
                    'price': r[2],
                    'living_area': r[3],
                    'url': r[4],
                    'status': r[5],
                    'seen_at': r[6],
                }
                for r in rows
            ]
    finally:
        conn.close()


def update_status(listing_id, status):
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                'update seen_listings set status = %s where listing_id = %s',
                (status, listing_id),
            )
            conn.commit()
    finally:
        conn.close()
