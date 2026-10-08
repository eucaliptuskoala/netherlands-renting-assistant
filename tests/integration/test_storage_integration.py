import os

import pytest
from dotenv import load_dotenv

import storage

load_dotenv()

has_db_url = bool(os.environ.get('SUPABASE_URL'))


@pytest.mark.integration
@pytest.mark.skipif(not has_db_url, reason='SUPABASE_URL not set')
def test_live_storage_init_and_query():
    # 1. Test database connection & schema initialization
    storage.init_db()

    # 2. Test reading active users
    active_users = storage.get_active_users()
    assert isinstance(active_users, list)

    if active_users:
        user = active_users[0]
        assert 'telegram_chat_id' in user
        assert 'city' in user
        assert 'bio' in user

    # 3. Test non-existent listing retrieval returns None
    listing = storage.get_listing('non-existent-test-id-999999')
    assert listing is None
