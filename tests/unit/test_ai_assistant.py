from unittest.mock import MagicMock, patch

import pytest

import services.ai_assistant as ai_module
from services import generate_cover_letter


@pytest.mark.unit
def test_missing_api_key_returns_warning(sample_user_profile, sample_listing):
    with patch.object(ai_module, '_get_client', return_value=None):
        result = generate_cover_letter(sample_user_profile, sample_listing)

        assert '⚠️ Error:' in result
        assert 'GEMINI_API_KEY' in result


@pytest.mark.unit
def test_missing_user_bio_returns_guidance(sample_user_no_bio, sample_listing, mock_gemini_client):
    with patch.object(ai_module, '_get_client', return_value=mock_gemini_client):
        result = generate_cover_letter(sample_user_no_bio, sample_listing)

        assert '⚠️ You have not set up your profile bio yet!' in result
        assert '📝 Edit Bio' in result
        # Should not make any API call to Gemini if bio is missing
        mock_gemini_client.models.generate_content.assert_not_called()


@pytest.mark.unit
def test_generate_cover_letter_success(sample_user_profile, sample_listing, mock_gemini_client):
    with patch.object(ai_module, '_get_client', return_value=mock_gemini_client):
        result = generate_cover_letter(sample_user_profile, sample_listing)

        assert 'Beste verhuurder' in result
        assert 'Kerkstraat 42' in result
        assert mock_gemini_client.models.generate_content.called

        # Verify arguments passed to model
        call_kwargs = mock_gemini_client.models.generate_content.call_args.kwargs
        contents = call_kwargs['contents']
        assert 'Kerkstraat 42' in contents
        assert '€1150' in contents
        assert 'Software Engineer at ASML' in contents


@pytest.mark.unit
def test_model_fallback_on_error(sample_user_profile, sample_listing):
    client = MagicMock()
    fallback_response = MagicMock()
    fallback_response.text = 'Cover letter from fallback model'

    # First model call raises 503 capacity error, second model call succeeds
    client.models.generate_content.side_effect = [
        RuntimeError('503 UNAVAILABLE: high demand'),
        fallback_response,
    ]

    with patch.object(ai_module, '_get_client', return_value=client):
        result = generate_cover_letter(sample_user_profile, sample_listing)

        assert result == 'Cover letter from fallback model'
        assert client.models.generate_content.call_count == 2


@pytest.mark.unit
def test_all_models_fail_returns_error_message(sample_user_profile, sample_listing):
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError('Connection failed')

    with patch.object(ai_module, '_get_client', return_value=client):
        result = generate_cover_letter(sample_user_profile, sample_listing)

        assert '⚠️ Gemini API error:' in result
        assert 'Connection failed' in result
