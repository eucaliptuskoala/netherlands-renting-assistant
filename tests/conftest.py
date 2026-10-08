from typing import Any
from unittest.mock import MagicMock

import pytest

from models import House


@pytest.fixture
def sample_user_profile() -> dict[str, Any]:
    return {
        'chat_id': 123456789,
        'username': 'ivan_test',
        'first_name': 'Ivan',
        'city': 'eindhoven',
        'min_price': 500,
        'max_price': 1300,
        'is_onboarded': True,
        'bio': 'Software Engineer at ASML, non-smoker, no pets, monthly income 4x rent requirement.',
    }


@pytest.fixture
def sample_user_no_bio() -> dict[str, Any]:
    return {
        'chat_id': 987654321,
        'username': 'alex_test',
        'first_name': 'Alex',
        'city': 'amsterdam',
        'min_price': 800,
        'max_price': 1600,
        'is_onboarded': True,
        'bio': None,
    }


@pytest.fixture
def sample_listing() -> dict[str, Any]:
    return {
        'listing_id': 'funda-123456',
        'address': 'Kerkstraat 42',
        'city': 'eindhoven',
        'price': 1150,
        'living_area': '58 m²',
        'url': 'https://www.funda.nl/detail/huur/eindhoven/appartement-kerkstraat-42/123456/',
        'status': 'new',
    }


@pytest.fixture
def sample_house_obj() -> House:
    return House(
        id='vestide-999',
        URL='https://rooms.vestide.nl/en/find-room/detail-accommodation/?detailId=999',
        address='Professor Holstlaan 1',
        price=650,
        living_area='24 m²',
    )


@pytest.fixture
def mock_gemini_client():
    client = MagicMock()
    response = MagicMock()
    response.text = (
        '### Dutch Version (Nederlands)\n'
        '```\n'
        'Beste verhuurder,\n\n'
        'Hierbij wil ik mijn interesse tonen in de woning aan de Kerkstraat 42.\n'
        '```\n\n'
        '### English Version\n'
        '```\n'
        'Dear Landlord,\n\n'
        'I am writing to express my interest in Kerkstraat 42.\n'
        '```'
    )
    client.models.generate_content.return_value = response
    return client
