# storage.py — Database layer for Supabase PostgreSQL
# Supports multi-user management, per-user listing statuses, and batched persistence.

import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _conn():
    """Create a new database connection. Returns None if SUPABASE_URL is not set."""
    url = os.environ.get('SUPABASE_URL')
    if not url:
        print(f'[{datetime.now():%H:%M:%S}] SUPABASE_URL not set', file=sys.stderr)
        return None
    return psycopg2.connect(url)


def init_db(default_chat_id: int | None = None) -> bool:
    """
    Initialize users and user_listings tables if they do not exist.
    Preserves all existing data in seen_listings and backfills data for default_chat_id.
    """
    conn = _conn()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            # 1. Create users table
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_chat_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    city TEXT NOT NULL DEFAULT 'eindhoven',
                    min_price INT NOT NULL DEFAULT 400,
                    max_price INT NOT NULL DEFAULT 1200,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    is_onboarded BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                '''
            )

            # Ensure is_onboarded and bio columns exist on existing installations
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_onboarded BOOLEAN NOT NULL DEFAULT true;')
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;')

            # 2. Create user_listings junction table
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS user_listings (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    listing_id TEXT NOT NULL REFERENCES seen_listings(listing_id) ON DELETE CASCADE,
                    status VARCHAR(20) NOT NULL DEFAULT 'new',
                    notified BOOLEAN NOT NULL DEFAULT false,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_user_listing UNIQUE (user_id, listing_id)
                );
                '''
            )

            # 3. Create indexes for quick lookups
            cur.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_user_listings_user_status ON user_listings(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_user_listings_listing_id ON user_listings(listing_id);
                CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(telegram_chat_id);
                '''
            )

            # 4. Add city column to seen_listings if it does not exist
            cur.execute(
                '''
                ALTER TABLE seen_listings ADD COLUMN IF NOT EXISTS city TEXT;
                UPDATE seen_listings SET city = 'eindhoven' WHERE city IS NULL;
                '''
            )

            # 5. Backfill existing author/default user if chat_id provided
            if default_chat_id:
                cur.execute(
                    '''
                    INSERT INTO users (telegram_chat_id, first_name, city, min_price, max_price, is_onboarded)
                    VALUES (%s, 'Owner', 'eindhoven', 400, 1200, true)
                    ON CONFLICT (telegram_chat_id) DO NOTHING;
                    ''',
                    (default_chat_id,),
                )

                cur.execute(
                    '''
                    INSERT INTO user_listings (user_id, listing_id, status, created_at, updated_at)
                    SELECT
                        u.id,
                        sl.listing_id,
                        COALESCE(sl.status, 'new'),
                        COALESCE(sl.seen_at, now()),
                        now()
                    FROM seen_listings sl
                    CROSS JOIN users u
                    WHERE u.telegram_chat_id = %s
                    ON CONFLICT (user_id, listing_id) DO NOTHING;
                    ''',
                    (default_chat_id,),
                )

            conn.commit()
            print(f'[{datetime.now():%H:%M:%S}] Database schema initialized successfully.')
            return True

    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] init_db failed: {e}', file=sys.stderr)
        return False
    finally:
        conn.close()


def get_or_create_user(
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
    default_onboarded: bool = False,
) -> dict[str, Any] | None:
    """Fetch existing user by telegram_chat_id or create a new user profile."""
    conn = _conn()
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO users (telegram_chat_id, username, first_name, city, min_price, max_price, is_onboarded)
                VALUES (%s, %s, %s, 'eindhoven', 400, 1200, %s)
                ON CONFLICT (telegram_chat_id) DO UPDATE
                  SET username = COALESCE(excluded.username, users.username),
                      first_name = COALESCE(excluded.first_name, users.first_name),
                      updated_at = now()
                RETURNING id, telegram_chat_id, username, first_name, city,
                          min_price, max_price, is_active, is_onboarded, bio;
                ''',
                (chat_id, username, first_name, default_onboarded),
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                return {
                    'id': row[0],
                    'telegram_chat_id': row[1],
                    'username': row[2],
                    'first_name': row[3],
                    'city': row[4],
                    'min_price': row[5],
                    'max_price': row[6],
                    'is_active': row[7],
                    'is_onboarded': row[8],
                    'bio': row[9] if len(row) > 9 else None,
                }
            return None
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] get_or_create_user failed: {e}', file=sys.stderr)
        return None
    finally:
        conn.close()


def get_active_users() -> list[dict[str, Any]]:
    """Return all active and fully onboarded users from database."""
    conn = _conn()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT id, telegram_chat_id, username, first_name, city,
                       min_price, max_price, is_active, is_onboarded, bio
                FROM users
                WHERE is_active = true AND is_onboarded = true
                ORDER BY id ASC;
                '''
            )
            rows = cur.fetchall()
            return [
                {
                    'id': r[0],
                    'telegram_chat_id': r[1],
                    'username': r[2],
                    'first_name': r[3],
                    'city': r[4],
                    'min_price': r[5],
                    'max_price': r[6],
                    'is_active': r[7],
                    'is_onboarded': r[8],
                    'bio': r[9] if len(r) > 9 else None,
                }
                for r in rows
            ]
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] get_active_users failed: {e}', file=sys.stderr)
        return []
    finally:
        conn.close()


def update_user_preferences(
    chat_id: int,
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    is_onboarded: bool | None = None,
) -> bool:
    """Update search city, price preferences, and onboarded status for a user."""
    conn = _conn()
    if not conn:
        return False

    updates = []
    values: list[Any] = []

    if city is not None:
        updates.append('city = %s')
        values.append(city.strip().lower())

    if min_price is not None:
        updates.append('min_price = %s')
        values.append(min_price)

    if max_price is not None:
        updates.append('max_price = %s')
        values.append(max_price)

    if is_onboarded is not None:
        updates.append('is_onboarded = %s')
        values.append(is_onboarded)

    if not updates:
        conn.close()
        return True

    updates.append('updated_at = now()')
    values.append(chat_id)

    try:
        with conn.cursor() as cur:
            query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_chat_id = %s"
            cur.execute(query, tuple(values))
            conn.commit()
            return True
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] update_user_preferences failed: {e}', file=sys.stderr)
        return False
    finally:
        conn.close()


def get_user_stats(chat_id: int) -> dict[str, int]:
    """Return count of new, accepted, and rejected listings for a specific user."""
    conn = _conn()
    if not conn:
        return {'new': 0, 'accepted': 0, 'rejected': 0}

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT ul.status, count(*)
                FROM user_listings ul
                JOIN users u ON u.id = ul.user_id
                WHERE u.telegram_chat_id = %s
                GROUP BY ul.status;
                ''',
                (chat_id,),
            )
            rows = cur.fetchall()
            counts = {'new': 0, 'accepted': 0, 'rejected': 0}
            for status, count in rows:
                if status in counts:
                    counts[status] = count
            return counts
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] get_user_stats failed: {e}', file=sys.stderr)
        return {'new': 0, 'accepted': 0, 'rejected': 0}
    finally:
        conn.close()


def save_and_assign_listings(
    houses: list[Any],
    city: str,
    target_users: list[dict[str, Any]],
) -> dict[int, int]:
    """
    Persist a batch of scraped houses and match them to target users in a SINGLE connection/transaction.
    Returns a dict mapping telegram_chat_id -> count of new listings assigned.
    """
    new_counts: dict[int, int] = defaultdict(int)
    if not houses or not target_users:
        return dict(new_counts)

    conn = _conn()
    if not conn:
        return dict(new_counts)

    try:
        with conn.cursor() as cur:
            for house in houses:
                listing_id = str(house.id)
                # 1. Upsert master catalog entry
                cur.execute(
                    '''
                    INSERT INTO seen_listings (listing_id, address, price, living_area, url, city, status, seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'new', now())
                    ON CONFLICT (listing_id) DO UPDATE
                      SET address = excluded.address,
                          price = excluded.price,
                          living_area = excluded.living_area,
                          url = excluded.url,
                          city = COALESCE(excluded.city, seen_listings.city);
                    ''',
                    (listing_id, house.address, str(house.price), house.living_area, house.URL, city),
                )

                # 2. Match against each target user
                for user in target_users:
                    u_min = user.get('min_price', 0)
                    u_max = user.get('max_price', 999999)

                    if (house.price == 0 and u_min == 0) or (u_min <= house.price <= u_max):
                        cur.execute(
                            '''
                            INSERT INTO user_listings (user_id, listing_id, status, notified, created_at, updated_at)
                            VALUES (%s, %s, 'new', false, now(), now())
                            ON CONFLICT (user_id, listing_id) DO NOTHING
                            RETURNING id;
                            ''',
                            (user['id'], listing_id),
                        )
                        if cur.fetchone() is not None:
                            new_counts[user['telegram_chat_id']] += 1

            conn.commit()
            return dict(new_counts)

    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] save_and_assign_listings failed: {e}', file=sys.stderr)
        conn.rollback()
        return dict(new_counts)
    finally:
        conn.close()


def get_listings_by_status(status: str, chat_id: int) -> list[dict[str, Any]]:
    """Return user-scoped listings filtered by status ('new', 'accepted', 'rejected')."""
    conn = _conn()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT s.listing_id, s.address, s.price, s.living_area, s.url, ul.status, ul.created_at, s.city
                FROM user_listings ul
                JOIN seen_listings s ON s.listing_id = ul.listing_id
                JOIN users u ON u.id = ul.user_id
                WHERE u.telegram_chat_id = %s AND ul.status = %s
                ORDER BY ul.created_at DESC;
                ''',
                (chat_id, status),
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
                    'city': r[7] if len(r) > 7 else 'eindhoven',
                }
                for r in rows
            ]
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] get_listings_by_status failed: {e}', file=sys.stderr)
        return []
    finally:
        conn.close()


def update_status(listing_id: str, status: str, chat_id: int) -> bool:
    """Update a listing's status ('accepted', 'rejected') for a specific user."""
    conn = _conn()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                UPDATE user_listings ul
                SET status = %s, updated_at = now()
                FROM users u
                WHERE ul.user_id = u.id
                  AND u.telegram_chat_id = %s
                  AND ul.listing_id = %s;
                ''',
                (status, chat_id, listing_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                print(
                    f'[{datetime.now():%H:%M:%S}] update_status: no matching listing {listing_id} for chat {chat_id}',
                    file=sys.stderr,
                )
                return False

            return True
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] update_status failed: {e}', file=sys.stderr)
        return False
    finally:
        conn.close()


def update_user_bio(chat_id: int, bio: str) -> bool:
    """Update applicant bio/profile text for a specific user."""
    conn = _conn()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                UPDATE users
                SET bio = %s, updated_at = now()
                WHERE telegram_chat_id = %s;
                ''',
                (bio.strip(), chat_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] update_user_bio failed: {e}', file=sys.stderr)
        return False
    finally:
        conn.close()


def get_listing(listing_id: str) -> dict[str, Any] | None:
    """Fetch single listing details from seen_listings catalog."""
    conn = _conn()
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT listing_id, address, price, living_area, url, city
                FROM seen_listings
                WHERE listing_id = %s;
                ''',
                (listing_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'listing_id': row[0],
                'address': row[1],
                'price': row[2],
                'living_area': row[3],
                'url': row[4],
                'city': row[5] or 'eindhoven',
            }
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] get_listing failed: {e}', file=sys.stderr)
        return None
    finally:
        conn.close()
