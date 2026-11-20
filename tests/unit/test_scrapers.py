from unittest.mock import MagicMock, patch

import pytest

from scrapers import Funda, Vestide, Xior
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


@pytest.mark.unit
def test_xior_connects_via_obscura_cdp():
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.contexts = [mock_context]

    mock_pw = MagicMock()
    mock_pw.chromium.connect_over_cdp.return_value = mock_browser

    with patch('scrapers.xior.sync_playwright') as mock_sync_pw:
        mock_sync_pw.return_value.__enter__.return_value = mock_pw

        xior = Xior(city='eindhoven', price=[0, 9000], cdp_url='http://127.0.0.1:9222')
        with patch.object(xior, '_scrape_property', return_value=[]):
            houses = xior.Run()

            mock_pw.chromium.connect_over_cdp.assert_called_once_with('http://127.0.0.1:9222')
            mock_pw.chromium.launch.assert_not_called()
            mock_page.close.assert_called_once()
            mock_browser.close.assert_called_once()
            assert houses == []


@pytest.mark.unit
def test_xior_fallback_to_local_chromium_on_cdp_failure():
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.connect_over_cdp.side_effect = RuntimeError('Connection refused')
    mock_pw.chromium.launch.return_value = mock_browser

    with patch('scrapers.xior.sync_playwright') as mock_sync_pw:
        mock_sync_pw.return_value.__enter__.return_value = mock_pw

        xior = Xior(city='eindhoven', price=[0, 9000], cdp_url='http://127.0.0.1:9222')
        with patch.object(xior, '_scrape_property', return_value=[]):
            houses = xior.Run()

            mock_pw.chromium.connect_over_cdp.assert_called_once_with('http://127.0.0.1:9222')
            mock_pw.chromium.launch.assert_called_once()
            assert houses == []
