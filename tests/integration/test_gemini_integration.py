import os

import pytest
from dotenv import load_dotenv

from services import generate_cover_letter

load_dotenv()

has_gemini_key = bool(os.environ.get('GEMINI_KEY') or os.environ.get('GEMINI_API_KEY'))


@pytest.mark.integration
@pytest.mark.skipif(not has_gemini_key, reason='GEMINI_KEY or GEMINI_API_KEY not set')
def test_live_gemini_cover_letter_generation(sample_user_profile, sample_listing):
    result = generate_cover_letter(sample_user_profile, sample_listing)

    # Must not contain error prefixes
    assert not result.startswith('⚠️')

    # Must contain code blocks for single-tap copying in Telegram
    assert '```' in result

    # Must mention Dutch and English versions
    assert 'Dutch' in result or 'Nederlands' in result
    assert 'English' in result

    # Must include context details from profile and listing
    assert 'Ivan' in result or 'Kerkstraat' in result
