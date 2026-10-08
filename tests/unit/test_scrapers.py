from unittest.mock import MagicMock, patch

import pytest

from scrapers import Funda, Vestide
from scrapers.base import RentProviderInterface


@pytest.mark.unit
def test_rent_provider_price_matching():
    provider = RentProviderInterface('eindhoven', [500, 1200])

    assert provider._isPriceMatched(500) is True
    assert provider._isPriceMatched(1200) is True
    assert provider._isPriceMatched(850) is True
    assert provider._isPriceMatched(499) is False
    assert provider._isPriceMatched(1201) is False


@pytest.mark.unit
def test_vestide_parser_success():
    sample_json = [
        {
            'id': 'abc-1',
            'advertentietitel': 'Kastanjelaan 12',
            'totaleHuur': '€680.00',
            'woonoppervlakte': 28.5,
        },
        {
            'id': 'abc-2',
            'advertentietitel': 'Too Expensive Studio',
            'totaleHuur': '€1500.00',
            'woonoppervlakte': 50,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.text = '{"dummy": "json"}'
    mock_resp.json.return_value = sample_json
    mock_resp.raise_for_status.return_value = None

    with patch('scrapers.vestide.curl_req.get', return_value=mock_resp):
        vestide = Vestide(city='eindhoven', price=[500, 1000])
        houses = vestide.Run()

        assert len(houses) == 1
        h = houses[0]
        assert h.id == 'vestide-abc-1'
        assert h.address == 'Kastanjelaan 12'
        assert h.price == 680
        assert h.living_area == '28 m²'
        assert 'detailId=abc-1' in h.URL


@pytest.mark.unit
def test_vestide_handles_network_error():
    with patch('scrapers.vestide.curl_req.get', side_effect=RuntimeError('Network unreachable')):
        vestide = Vestide(city='eindhoven', price=[500, 1000])
        houses = vestide.Run()

        assert houses == []


@pytest.mark.unit
def test_funda_parser_success():
    sample_html = """
    <html>
      <body>
        <div>
          <div>
            <a data-testid="listingDetailsAddress" href="/detail/huur/eindhoven/appartement-keizersgracht-10/4321/">
              <span>Keizersgracht 10</span>
            </a>
            <div>€ 1.100 /mnd</div>
          </div>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.text = sample_html
    mock_resp.raise_for_status.return_value = None

    with patch('scrapers.funda.curl_req.get', return_value=mock_resp):
        funda = Funda(city='eindhoven', price=[500, 1500])
        houses = funda.Run()

        assert len(houses) == 1
        h = houses[0]
        assert h.id == '4321'
        assert h.address == 'Keizersgracht 10'
        assert h.price == 1100
        assert 'https://www.funda.nl/detail/huur/eindhoven' in h.URL


@pytest.mark.unit
def test_funda_handles_network_error():
    with patch('scrapers.funda.curl_req.get', side_effect=RuntimeError('Connection reset')):
        funda = Funda(city='eindhoven', price=[500, 1500])
        houses = funda.Run()

        assert houses == []
