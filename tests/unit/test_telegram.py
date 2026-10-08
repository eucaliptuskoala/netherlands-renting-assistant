from unittest.mock import MagicMock, patch

import pytest
import requests

from main import send_telegram_notification


@pytest.mark.unit
def test_send_telegram_notification_success():
    mock_resp = MagicMock()
    mock_resp.ok = True

    with patch('requests.post', return_value=mock_resp) as mock_post:
        result = send_telegram_notification('test-token', 123456789, 'Hello world')

        assert result is True
        mock_post.assert_called_once_with(
            'https://api.telegram.org/bottest-token/sendMessage',
            json={'chat_id': 123456789, 'text': 'Hello world'},
            timeout=10,
        )


@pytest.mark.unit
def test_send_telegram_notification_http_failure():
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 400
    mock_resp.text = 'Bad Request: chat not found'

    with patch('requests.post', return_value=mock_resp):
        result = send_telegram_notification('test-token', 123456789, 'Hello world')

        assert result is False


@pytest.mark.unit
def test_send_telegram_notification_network_exception():
    with patch('requests.post', side_effect=requests.exceptions.ConnectTimeout('Timed out')):
        result = send_telegram_notification('test-token', 123456789, 'Hello world')

        assert result is False
